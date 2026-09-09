"""Production roles for the NFL recommendation service.

The API role is read-only. The worker is the only role that writes freezes and
artifacts, and it has no provider submission capability. Migration is an
explicit one-shot command so a web restart cannot alter the database schema.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from oracle_core.artifacts import atomic_write_json
from oracle_core.storage import PoolOptions, create_postgres_engine
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from nfl_oracle.contests.boosts import BoostObservation
from nfl_oracle.recommendations.context import build_context, enrich_historical_rows
from nfl_oracle.recommendations.history import load_history, load_history_metadata
from nfl_oracle.recommendations.pipeline import (
    ModelBundle,
    PipelinePolicy,
    RecommendationPipeline,
    freeze_dry_run,
)
from nfl_oracle.recommendations.provider import NFLReader, NoSlate, ObservationStore, parse_game
from nfl_oracle.recommendations.schema import Contest, Slate, fingerprint
from nfl_oracle.recommendations.sources import (
    ContextSnapshot,
    add_weather_for_slate,
    load_venues,
)
from nfl_oracle.recommendations.store import RecommendationStore, migrate


def _project_root() -> Path:
    configured = os.environ.get("NFL_PROJECT_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    local = Path("nfl-oracle")
    return (local if local.is_dir() else Path.cwd()).resolve()


def _engine() -> Any:
    value = os.environ.get("NFL_DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("NFL_DATABASE_URL_required")
    if value.startswith("sqlite:"):
        return create_engine(value)
    return create_postgres_engine(
        value,
        pool=PoolOptions(pool_size=3, max_overflow=2, pool_timeout=5),
        connect_args={"connect_timeout": 5},
    )


def _freeze_engine(project: Path) -> Engine:
    """The ``freeze`` command's store backend: explicit Postgres if configured,
    otherwise a private local sqlite file so a laptop with no database
    configured can still run it end to end.

    An explicitly configured ``NFL_DATABASE_URL`` (Postgres or sqlite) is
    never auto-migrated here; the operator runs ``nfl-pipeline migrate`` for
    that, matching every other role in this file. The sqlite fallback is a
    scratch file this command itself owns, so creating its schema on first
    use is not the production migration step this file otherwise keeps
    explicit.
    """
    configured = os.environ.get("NFL_DATABASE_URL", "").strip()
    if configured:
        return _engine()  # type: ignore[no-any-return]
    fallback = project / "data" / "nfl_pipeline_freeze.sqlite3"
    fallback.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{fallback}")
    migrate(engine)
    return engine


def _day(value: str | None) -> date | None:
    if not value:
        return None
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise RuntimeError("NFL_SLATE_DATE_invalid") from None
    return None


def _latest_context(project: Path) -> Path:
    explicit = os.environ.get("NFL_CONTEXT_SNAPSHOT", "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise RuntimeError("NFL_CONTEXT_SNAPSHOT_missing")
        return path
    paths = list((project / "data" / "artifacts" / "context").glob("*.json"))
    paths.extend((project / "data" / "artifacts" / "context").glob("**/*.json"))
    unique = {path.resolve(): path for path in paths if path.is_file()}
    if not unique:
        raise RuntimeError("context_snapshot_missing")
    return max(unique.values(), key=lambda path: path.stat().st_mtime)


def _load_context(project: Path, slate: Any, now: datetime) -> ContextSnapshot:
    snapshot = ContextSnapshot.load(_latest_context(project))
    venues_path = Path(
        os.environ.get("NFL_VENUE_CONFIG", str(project / "config" / "NFLconfigvenues.json"))
    )
    if not venues_path.is_file():
        raise RuntimeError("venue_config_missing")
    venues = load_venues(venues_path)
    weather = [source for key, source in snapshot.sources.items() if key.startswith("weather:")]
    stale_weather = not weather or any(
        source.status not in {"available", "indoor"}
        or (now - source.clock.captured_at).total_seconds() > 6 * 3600
        for source in weather
    )
    if stale_weather:
        with httpx.Client(
            timeout=25,
            headers={"User-Agent": "NFL Oracle forecast contact operator"},
        ) as client:
            snapshot = add_weather_for_slate(
                snapshot, slate, venues, client=client, clock=lambda: now
            )
        snapshot.save(project / "data" / "artifacts")
    return snapshot


def _model_bundle(project: Path, snapshot: ContextSnapshot, now: datetime) -> ModelBundle:
    root = Path(os.environ.get("NFL_HISTORY_ROOT", str(project / "data" / "raw" / "corpus_g")))
    rows, excluded = load_history(root)
    if len(rows) < 30:
        raise RuntimeError("historical_training_rows_insufficient")
    metadata = load_history_metadata(root, rows)
    enrichment = enrich_historical_rows(rows, snapshot, metadata=metadata)
    from nfl_oracle.recommendations.model import attach_enrichment, fit_model

    enriched = attach_enrichment(rows, enrichment)
    model = fit_model(enriched, trained_at=now)
    return ModelBundle(
        model=model,
        history=tuple(enriched),
        source_hashes=tuple(source.sha256 for source in snapshot.sources.values()),
        audit={
            "history_root": str(root),
            "history_rows": len(rows),
            "history_excluded": excluded,
            "context_rows": len(enrichment.rows),
            "context_excluded": enrichment.excluded,
            "context_evidence_mode": enrichment.evidence_mode,
            "contest_entry": False,
        },
    )


def _ensure_model(
    project: Path,
    store: RecommendationStore,
    pipeline: RecommendationPipeline,
    snapshot: ContextSnapshot,
    now: datetime,
) -> str:
    """Load a valid active model or train and activate one from mounted evidence."""
    try:
        return pipeline.active_model()[0]
    except ValueError:
        bundle = _model_bundle(project, snapshot, now)
        return pipeline.activate_model(bundle)


def _policy() -> PipelinePolicy:
    enabled = os.environ.get("NFL_RECOMMENDATIONS_ENABLED", "0").lower() in {
        "1",
        "true",
        "yes",
    }
    return PipelinePolicy(recommendations_enabled=enabled)


def _empty_boost_observation(contest_id: int, *, captured_at: str) -> BoostObservation:
    return BoostObservation(
        contest_id=contest_id,
        captured_at=captured_at,
        n_players=0,
        n_nonzero=0,
        max_boost=0.0,
        distinct_boosts=(),
        published=False,
    )


def _latest_boost_observation(path: Path, contest_id: int, *, now: datetime) -> BoostObservation:
    """The most recent ``nfl-boost-watch`` observation for this contest.

    Absent a series file, or with no row for this contest, this returns an
    explicit ``n_players=0`` observation, which G4 (``gate_boost_regime``)
    reports as an ``undetermined`` regime rather than a passing one -- an
    unread series is never silently treated as a published or zero table.
    """
    if not path.is_file():
        return _empty_boost_observation(contest_id, captured_at=now.isoformat())
    latest: dict[str, Any] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        row = json.loads(stripped)
        if row.get("contest_id") == contest_id:
            latest = row
    if latest is None:
        return _empty_boost_observation(contest_id, captured_at=now.isoformat())
    return BoostObservation(
        contest_id=int(latest["contest_id"]),
        captured_at=str(latest["captured_at"]),
        n_players=int(latest["n_players"]),
        n_nonzero=int(latest["n_nonzero"]),
        max_boost=float(latest["max_boost"]),
        distinct_boosts=tuple(float(v) for v in latest.get("distinct_boosts", ())),
        published=bool(latest["published"]),
        source=str(latest.get("source", "prelock_rating_search")),
    )


def _freeze_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    freeze = commands.add_parser(
        "freeze",
        help="run G1-G7 and either print five picks in committed slot order, or refuse",
    )
    freeze.add_argument("--contest-id", type=int, required=True)
    freeze.add_argument(
        "--slate-path", required=True, help="path to a captured Slate JSON artifact"
    )
    freeze.add_argument(
        "--recheck-slate-path",
        default=None,
        help=(
            "path to an independently re-captured Slate JSON artifact for G5's "
            "contest-state recheck; omit to have G5 refuse explicitly rather "
            "than assume the original capture's contest state still holds"
        ),
    )
    freeze.add_argument("--boost-watch-path", default=None)
    freeze.add_argument("--out-dir", default=None)
    freeze.add_argument(
        "--max-input-age-seconds", type=int, default=900, help="G2 policy, 60-900"
    )
    freeze.add_argument("--max-model-age-days", type=int, default=8, help="G6 policy, 1-30")
    freeze.add_argument(
        "--dry-run",
        action="store_true",
        help="skip the T-40 freeze-window check; every other gate still applies",
    )


def _freeze(args: argparse.Namespace) -> int:
    project = _project_root()
    now = datetime.now(UTC)

    slate_path = Path(args.slate_path).expanduser()
    if not slate_path.is_file():
        print(
            json.dumps(
                {"status": "refused", "reason": "slate_path_missing", "path": str(slate_path)}
            )
        )
        return 1
    slate = Slate.model_validate(json.loads(slate_path.read_text(encoding="utf-8")))
    if slate.contest.contest_id != args.contest_id:
        print(
            json.dumps(
                {
                    "status": "refused",
                    "reason": "slate_contest_id_mismatch",
                    "expected_contest_id": args.contest_id,
                    "slate_contest_id": slate.contest.contest_id,
                }
            )
        )
        return 1

    current_contest: Contest | None = None
    refetch_error: str | None = None
    if args.recheck_slate_path:
        recheck_path = Path(args.recheck_slate_path).expanduser()
        if not recheck_path.is_file():
            refetch_error = "recheck_slate_path_missing"
        else:
            try:
                recheck_slate = Slate.model_validate(
                    json.loads(recheck_path.read_text(encoding="utf-8"))
                )
                current_contest = recheck_slate.contest
            except (json.JSONDecodeError, ValueError) as error:
                refetch_error = f"recheck_slate_invalid:{type(error).__name__}"
    else:
        refetch_error = "no_recheck_slate_path_given"

    default_boost_path = project / "data" / "artifacts" / "boost_watch.jsonl"
    boost_path = Path(args.boost_watch_path or default_boost_path)
    observation = _latest_boost_observation(boost_path, args.contest_id, now=now)

    engine = _freeze_engine(project)
    store = RecommendationStore(engine, writable=True)
    policy = PipelinePolicy(
        recommendations_enabled=True,
        input_max_age_seconds=args.max_input_age_seconds,
        model_max_age_days=args.max_model_age_days,
    )
    pipeline = RecommendationPipeline(store, policy=policy, clock=lambda: datetime.now(UTC))

    try:
        snapshot = _load_context(project, slate, now)
        _ensure_model(project, store, pipeline, snapshot, now)
        context = build_context(slate, snapshot, now)
    except Exception as error:  # noqa: BLE001 - reported as a labeled, value-free refusal
        print(
            json.dumps(
                {
                    "status": "refused",
                    "reason": "context_or_model_preparation_failed",
                    "error_type": type(error).__name__,
                    "detail": str(error),
                }
            )
        )
        return 1

    outcome = freeze_dry_run(
        pipeline,
        slate=slate,
        context=context,
        boost_observation=observation,
        current_contest=current_contest,
        refetch_error=refetch_error,
        now=now,
        require_freeze_window=not args.dry_run,
    )

    if outcome.artifact is None:
        refusal = {"status": "refused", **outcome.gate_report.to_json_obj()}
        print(json.dumps(refusal, sort_keys=True))
        return 1

    out_dir = Path(args.out_dir).expanduser() if args.out_dir else project / "data" / "artifacts"
    digest = fingerprint(outcome.artifact)
    out_path = out_dir / f"freeze_{args.contest_id}_{digest}.json"
    if not out_path.exists():
        atomic_write_json(out_path, outcome.artifact, mode=0o600)
    print(
        json.dumps(
            {"status": "ready", "artifact_path": str(out_path), **outcome.artifact}, sort_keys=True
        )
    )
    return 0


async def _worker_once(
    project: Path,
    store: RecommendationStore,
    pipeline: RecommendationPipeline,
    requested_day: date | None,
) -> dict[str, Any] | None:
    headers_from = os.environ.get("NFL_REALSPORTS_STORAGE_STATE", "")
    del headers_from  # The provider module reads its own scoped environment path.
    from nfl_oracle.ingest.realsports import headers_or_capture

    headers = await headers_or_capture()
    async with httpx.AsyncClient(timeout=25) as client:
        reader = NFLReader(
            client,
            headers,
            ObservationStore(project / "data" / "raw" / "observations"),
        )
        day = requested_day or await reader.next_day()
        content = await reader.day_content(day)
        games = tuple(parse_game(raw) for raw in content.get("games", []))
        if not games:
            store.record_run(day, status="no_slate", detail_code="no_games")
            return None
        cutoff = min(game.kickoff_at for game in games)
        now = datetime.now(UTC)
        due = cutoff - timedelta(minutes=40)
        if now >= cutoff:
            store.record_run(day, status="locked", detail_code="slate_cutoff_passed")
            return None
        if now < due:
            store.record_run(
                day,
                status="waiting",
                detail_code="waiting_for_t40",
                details={"next_freeze": due.isoformat(), "cutoff_at": cutoff.isoformat()},
            )
            return None
        available = content.get("config", {}).get("dailyDraftInfo", {}).get("contests", [])
        contest_ids = [item.get("id") for item in available if isinstance(item, dict)]
        if len(contest_ids) != 1 or type(contest_ids[0]) is not int:
            store.record_run(day, status="blocked", detail_code="contest_unavailable")
            return None
        slate = await reader.collect(day, contest_id=contest_ids[0])
        # Collection is a live network round trip; every per-candidate and
        # context clock it produces is stamped with real wall-clock time at or
        # after this point. Re-read the clock here rather than reusing the
        # pre-collection `now` above, or `assert_available` sees its own
        # freshly collected evidence as being from the future and refuses.
        decision_at = datetime.now(UTC)
        snapshot = _load_context(project, slate, decision_at)
        _ensure_model(project, store, pipeline, snapshot, decision_at)
        context = build_context(slate, snapshot, decision_at)
        pipeline.prepare(slate, context)
        return await pipeline.publish(day, reader)


async def _run_worker(once: bool, poll_seconds: int, requested_day: date | None) -> int:
    project = _project_root()
    engine = _engine()
    store = RecommendationStore(engine, writable=True)
    policy = _policy()
    if not policy.recommendations_enabled:
        print(json.dumps({"status": "blocked", "detail_code": "recommendations_disabled"}))
        return 1
    pipeline = RecommendationPipeline(store, policy=policy)
    while True:
        try:
            record = await _worker_once(project, store, pipeline, requested_day)
            if record is not None:
                print(
                    json.dumps({"status": "ready", "slate_date": record["slate_date"], "picks": 5})
                )
            else:
                print(json.dumps({"status": "waiting_or_locked"}))
        except NoSlate as error:
            day = requested_day or datetime.now(UTC).date()
            store.record_run(day, status="no_slate", detail_code=str(error))
            print(json.dumps({"status": "no_slate"}))
        except Exception as error:
            day = requested_day or datetime.now(UTC).date()
            store.record_run(day, status="error", detail_code=type(error).__name__.lower())
            print(json.dumps({"status": "error", "error_type": type(error).__name__}))
            if once:
                return 1
        if once:
            return 0
        await asyncio.sleep(max(10, min(poll_seconds, 60)))


def _train() -> int:
    project = _project_root()
    now = datetime.now(UTC)
    snapshot = ContextSnapshot.load(_latest_context(project))
    store = RecommendationStore(_engine(), writable=True)
    pipeline = RecommendationPipeline(store, policy=_policy())
    digest = _ensure_model(project, store, pipeline, snapshot, now)
    model = pipeline.active_model()[1].model
    print(
        json.dumps(
            {
                "status": "trained",
                "model_sha256": digest,
                "selected_estimator": model.selected_estimator,
                "training_rows": model.training_rows,
                "holdout_rows": model.evaluation.get("holdout_rows"),
                "contest_entry": False,
            }
        )
    )
    return 0


def _serve(host: str, port: int) -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn_required", file=sys.stderr)
        return 1
    uvicorn.run(
        "nfl_oracle.recommendations.app:app_from_env",
        factory=True,
        host=host,
        port=port,
        access_log=False,
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nfl-pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    migrate_command = commands.add_parser("migrate")
    migrate_command.set_defaults()
    commands.add_parser("train")
    worker = commands.add_parser("worker")
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--poll-seconds", type=int, default=30)
    worker.add_argument("--day")
    _freeze_parser(commands)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "serve":
        return _serve(args.host, args.port)
    if args.command == "migrate":
        migrate(_engine())
        print(json.dumps({"status": "migrated", "contest_entry": False}))
        return 0
    if args.command == "train":
        return _train()
    if args.command == "freeze":
        return _freeze(args)
    requested_day = _day(args.day or os.environ.get("NFL_SLATE_DATE"))
    return asyncio.run(_run_worker(args.once, args.poll_seconds, requested_day))


if __name__ == "__main__":
    raise SystemExit(main())
