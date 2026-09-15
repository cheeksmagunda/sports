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


def _latest_context(project: Path) -> Path | None:
    """Return the newest on-disk context snapshot path, or None if absent.

    Explicit NFL_CONTEXT_SNAPSHOT still fails closed when set but missing.
    """
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
        return None
    return max(unique.values(), key=lambda path: path.stat().st_mtime)


def _context_seasons(now: datetime) -> list[int]:
    """Seasons to pull for a cold-start nflverse context bootstrap."""
    year = now.astimezone(UTC).year
    return [year - 2, year - 1, year]


def _season_match(raw: Any, season: int) -> bool:
    try:
        return int(raw) == int(season)
    except (TypeError, ValueError):
        return False


def _schedules_cover_slate(snapshot: ContextSnapshot, slate: Any) -> bool:
    """True when schedules can join every slate game by season/gameday/teams."""
    from zoneinfo import ZoneInfo

    schedules = snapshot.sources.get("schedules")
    if schedules is None or not schedules.rows:
        return False
    eastern = ZoneInfo("America/New_York")
    for game in slate.games:
        gameday = game.kickoff_at.astimezone(eastern).date().isoformat()
        hits = [
            row
            for row in schedules.rows
            if _season_match(row.get("season"), game.season)
            and str(row.get("gameday")) == gameday
            and str(row.get("home_team")) == game.home_team
            and str(row.get("away_team")) == game.away_team
        ]
        if len(hits) != 1:
            return False
    return True


def _bootstrap_context(project: Path, now: datetime) -> ContextSnapshot:
    """Cold-start nflverse context when the volume has no snapshot yet.

    Week-2 / TNF freezes fail hard on context_snapshot_missing if the worker
    image has no baked-in artifacts and the volume was wiped or never seeded.
    Public nflverse schedules/rosters/stats need no Real Sports auth.
    """
    from nfl_oracle.recommendations.sources import collect_nflverse

    snapshot = collect_nflverse(_context_seasons(now), clock=lambda: now)
    snapshot.save(project / "data" / "artifacts")
    return snapshot


def _load_context(project: Path, slate: Any, now: datetime) -> ContextSnapshot:
    path = _latest_context(project)
    if path is None:
        snapshot = _bootstrap_context(project, now)
    else:
        snapshot = ContextSnapshot.load(path)
        # Stale snapshots collected before the 2026 schedule published cannot
        # join TNF/Sunday stadium weather. Refresh nflverse sources in place.
        if not _schedules_cover_slate(snapshot, slate):
            snapshot = _bootstrap_context(project, now)
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


def _already_frozen(store: RecommendationStore, day: date) -> bool:
    """Report whether this slate already has a published lineup.

    The freeze is a decision a person acts on. Once it is on the page the
    operator may already have entered it, so re-running the pipeline and
    writing a second, different lineup does not correct anything -- it creates
    a second truth they never saw. Without this the worker re-collected and
    re-froze on every poll until kickoff: 19 freezes on 2026-09-09 and 20 on
    2026-09-10, each one a full provider sweep.

    Deliberately fails open. If the store cannot answer, the freeze proceeds,
    because a duplicate lineup is a far smaller failure than a missing one.
    """
    try:
        frozen = store.latest(day)
    except Exception:
        return False
    if not frozen:
        return False
    try:
        cutoff = datetime.fromisoformat(frozen["cutoff_at"])
    except (KeyError, TypeError, ValueError):
        return False
    # Past the cutoff the slate is closed and publish() already refuses; let it
    # take that path so the run record keeps saying "locked" rather than "ready".
    return datetime.now(UTC) < cutoff


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
        if _already_frozen(store, day):
            store.record_run(day, status="ready", detail_code="already_frozen_for_slate")
            return None
        content = await reader.day_content(day)
        games = tuple(parse_game(raw) for raw in content.get("games", []))
        if not games:
            store.record_run(day, status="no_slate", detail_code="no_games")
            return None
        now = datetime.now(UTC)
        # A Sunday slate has many kickoffs. Gating on min(kickoff) across every
        # game means the first kickoff of the day locks out every later window,
        # so an afternoon or night contest could never freeze. Gate on the next
        # game that has not started yet; the provider's own contest lock state
        # still refuses a contest whose games are already under way.
        upcoming = tuple(game for game in games if game.kickoff_at > now)
        if not upcoming:
            store.record_run(day, status="locked", detail_code="slate_cutoff_passed")
            return None
        cutoff = min(game.kickoff_at for game in upcoming)
        due = cutoff - timedelta(minutes=40)
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
        # The active bundle's finalized history is the Real-value archive the
        # opponent-defense priors join against. Reuse it rather than re-reading
        # Corpus G; the walk-forward cutoff keeps same-slate finals out.
        _, active = pipeline.active_model()
        context = build_context(slate, snapshot, decision_at, value_history=active.history)
        pipeline.prepare(slate, context)
        return await pipeline.publish(day, reader)


def _record_worker_failure(
    store: RecommendationStore,
    day: date,
    *,
    status: str,
    detail_code: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Keep the poll loop alive when its failure audit store is unavailable."""
    try:
        store.record_run(day, status=status, detail_code=detail_code, details=details or {})
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
            # Recording only the exception type leaves a refused freeze
            # undiagnosable after the fact: every gate failure arrives as a bare
            # "valueerror" and the slate is gone before anyone can reproduce it.
            # Gate failures raise ValueError with an internal reason code, which
            # is safe to keep. Other exception types can carry provider URLs or
            # query values, so those stay type-only.
            reason = str(error)[:200] if type(error) is ValueError else ""
            _record_worker_failure(
                store,
                day,
                status="error",
                detail_code=type(error).__name__.lower(),
                details={"reason": reason} if reason else None,
            )
            print(
                json.dumps(
                    {"status": "error", "error_type": type(error).__name__, "reason": reason}
                )
            )
            if once:
                return 1
        if once:
            return 0
        await asyncio.sleep(max(10, min(poll_seconds, 60)))


def _train(*, force: bool = False) -> int:
    project = _project_root()
    now = datetime.now(UTC)
    context_path = _latest_context(project)
    if context_path is None:
        snapshot = _bootstrap_context(project, now)
    else:
        snapshot = ContextSnapshot.load(context_path)
    store = RecommendationStore(_engine(), writable=True)
    pipeline = RecommendationPipeline(store, policy=_policy())
    if force:
        # `_ensure_model` returns the active model untouched whenever it is
        # still inside `model_max_age_days`, which is the right behaviour for
        # the worker but makes a weekly retrain a no-op: the model only gets
        # rebuilt once it has already expired, which is precisely the freeze it
        # would otherwise refuse. A scheduled retrain has to be able to say
        # "rebuild now" and reset the staleness clock ahead of the deadline.
        bundle = _model_bundle(project, snapshot, now)
        digest = pipeline.activate_model(bundle)
        retrained = True
    else:
        previous = None
        try:
            previous = pipeline.active_model()[0]
        except ValueError:
            previous = None
        digest = _ensure_model(project, store, pipeline, snapshot, now)
        retrained = digest != previous
    model = pipeline.active_model()[1].model
    print(
        json.dumps(
            {
                "status": "trained" if retrained else "reused_active_model",
                "retrained": retrained,
                "model_sha256": digest,
                "trained_at": model.trained_at.isoformat(),
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


def _sweep_week_dayclose(
    store: RecommendationStore,
    project: Path,
    gamedays: list[date],
    *,
    catchup_window_days: int,
) -> dict[str, str]:
    """Grade every week gameday that has a freeze but no dayclose_grade yet.

    Reuses dayclose.run's single-day grading path per day rather than
    inventing a second refresh stack; catchup_window_days is passed straight
    through and defaults small here since the caller already knows exactly
    which days belong to this week.
    """
    from nfl_oracle.recommendations.dayclose import dayclose_grade_kind
    from nfl_oracle.recommendations.dayclose import run as run_dayclose

    outcomes: dict[str, str] = {}
    for day in gamedays:
        if store.latest(day) is None:
            continue
        if store.latest_artifact(dayclose_grade_kind(day)) is not None:
            continue
        result = run_dayclose(
            store,
            project_root=project,
            target_day=day,
            catchup_window_days=catchup_window_days,
        )
        outcomes[day.isoformat()] = result["status"]
    return outcomes


def _weekclose(
    *,
    season_arg: int | None,
    week_arg: int | None,
    as_of_arg: str | None,
    with_dayclose: bool,
    catchup_window_days: int,
) -> int:
    from nfl_oracle.calendar.schedule import resolve_schedule_csv_path, try_load_schedules_csv
    from nfl_oracle.contests.store import ContestStore
    from nfl_oracle.data.paths import resolve_data_paths
    from nfl_oracle.recommendations.weekclose import (
        build_and_persist_week_punch_list,
        resolve_week_gamedays,
    )

    project = _project_root()
    as_of = _day(as_of_arg)
    store = RecommendationStore(_engine(), writable=True)
    paths = resolve_data_paths(project)
    games = try_load_schedules_csv(resolve_schedule_csv_path(paths.root))

    if with_dayclose:
        _slate, gamedays = resolve_week_gamedays(
            games, season=season_arg, week=week_arg, as_of=as_of
        )
        _sweep_week_dayclose(store, project, gamedays, catchup_window_days=catchup_window_days)

    contest_store = ContestStore(project=project)
    result = build_and_persist_week_punch_list(
        store,
        games,
        season=season_arg,
        week=week_arg,
        as_of=as_of,
        contest_store=contest_store,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


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
    train = commands.add_parser(
        "train", help="ensure an active model exists, or rebuild one with --force"
    )
    train.add_argument(
        "--force",
        action="store_true",
        help=(
            "retrain and activate even when the active model is still inside "
            "its age limit, resetting the staleness clock; this is what a "
            "weekly scheduled retrain needs"
        ),
    )
    dayclose = commands.add_parser("dayclose")
    dayclose.add_argument("--day")
    dayclose.add_argument("--catchup-window-days", type=int, default=7)
    weekclose = commands.add_parser("weekclose")
    weekclose.add_argument("--season", type=int)
    weekclose.add_argument("--week", type=int)
    weekclose.add_argument("--as-of")
    weekclose.add_argument("--with-dayclose", action="store_true")
    weekclose.add_argument("--catchup-window-days", type=int, default=1)
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
        return _train(force=args.force)
    if args.command == "dayclose":
        return _dayclose(args.day, catchup_window_days=args.catchup_window_days)
    if args.command == "weekclose":
        return _weekclose(
            season_arg=args.season,
            week_arg=args.week,
            as_of_arg=args.as_of,
            with_dayclose=args.with_dayclose,
            catchup_window_days=args.catchup_window_days,
        )
    if args.command == "backup-export":
        return _backup_export()
    if args.command == "backup-restore":
        return _backup_restore(args.file, migrate_first=args.migrate)
    requested_day = _day(args.day or os.environ.get("NFL_SLATE_DATE"))
    return asyncio.run(_run_worker(args.once, args.poll_seconds, requested_day))


if __name__ == "__main__":
    raise SystemExit(main())
