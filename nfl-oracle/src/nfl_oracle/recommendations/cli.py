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
from oracle_core.storage import PoolOptions, create_postgres_engine
from sqlalchemy import create_engine

from nfl_oracle.recommendations.context import build_context, enrich_historical_rows
from nfl_oracle.recommendations.history import load_history, load_history_metadata
from nfl_oracle.recommendations.pipeline import (
    ModelBundle,
    PipelinePolicy,
    RecommendationPipeline,
)
from nfl_oracle.recommendations.provider import NFLReader, NoSlate, ObservationStore, parse_game
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
    from nfl_oracle.recommendations.model import (
        attach_enrichment,
        drop_ambiguous_identity_rows,
        fit_model,
    )

    enriched = attach_enrichment(rows, enrichment)
    # A same-name identity-crosswalk collision (one internal player_id maps to
    # two different real players' external ids across games) is a genuine
    # data ambiguity that fit_model's own _validate_identity_links correctly
    # refuses to train on. Drop just the affected player_id(s) rather than
    # weakening that check; both `enriched` (stored below) and what fit_model
    # sees must be the same filtered set, or the training fingerprint the
    # model records will not match the history this bundle persists.
    enriched, identity_audit = drop_ambiguous_identity_rows(enriched)
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
            **identity_audit,
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


def _record_worker_failure(
    store: RecommendationStore, day: date, *, status: str, detail_code: str
) -> None:
    """Keep the poll loop alive when its failure audit store is unavailable."""
    try:
        store.record_run(day, status=status, detail_code=detail_code)
    except Exception as error:
        # A transient database outage can cause both the poll and this audit
        # write to fail. Never let the second failure stop future retries or
        # print connection details from the database exception.
        print(
            json.dumps(
                {
                    "status": "error",
                    "detail_code": "worker_run_record_failed",
                    "error_type": type(error).__name__,
                }
            )
        )


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
            _record_worker_failure(store, day, status="no_slate", detail_code=str(error))
            print(json.dumps({"status": "no_slate"}))
        except Exception as error:
            day = requested_day or datetime.now(UTC).date()
            _record_worker_failure(
                store, day, status="error", detail_code=type(error).__name__.lower()
            )
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


def _read_json_payload(path: str) -> dict[str, Any]:
    if path == "-":
        payload = json.load(sys.stdin)
    else:
        with Path(path).expanduser().open(encoding="utf-8") as handle:
            payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError("json_object_required")
    return payload


def _dayclose(day_arg: str | None, *, catchup_window_days: int) -> int:
    from nfl_oracle.recommendations.dayclose import run as run_dayclose

    store = RecommendationStore(_engine(), writable=True)
    target_day = _day(day_arg)
    result = run_dayclose(
        store,
        project_root=_project_root(),
        target_day=target_day,
        catchup_window_days=catchup_window_days,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 1 if result["status"] == "failed" else 0


def _backup_export() -> int:
    store = RecommendationStore(_engine())
    print(json.dumps(store.export_backup(), sort_keys=True, separators=(",", ":")))
    return 0


def _backup_restore(path: str, *, migrate_first: bool) -> int:
    engine = _engine()
    if migrate_first:
        migrate(engine)
    store = RecommendationStore(engine, writable=True)
    store.restore_backup(_read_json_payload(path))
    print(json.dumps({"status": "restored", "contest_entry": False}))
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
    dayclose = commands.add_parser("dayclose")
    dayclose.add_argument("--day")
    dayclose.add_argument("--catchup-window-days", type=int, default=7)
    commands.add_parser("backup-export")
    restore = commands.add_parser("backup-restore")
    restore.add_argument("--file", default="-")
    restore.add_argument("--migrate", action="store_true")
    worker = commands.add_parser("worker")
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--poll-seconds", type=int, default=30)
    worker.add_argument("--day")
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
    if args.command == "dayclose":
        return _dayclose(args.day, catchup_window_days=args.catchup_window_days)
    if args.command == "backup-export":
        return _backup_export()
    if args.command == "backup-restore":
        return _backup_restore(args.file, migrate_first=args.migrate)
    requested_day = _day(args.day or os.environ.get("NFL_SLATE_DATE"))
    return asyncio.run(_run_worker(args.once, args.poll_seconds, requested_day))


if __name__ == "__main__":
    raise SystemExit(main())
