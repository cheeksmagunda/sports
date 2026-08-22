"""Watchdog pipeline-health checks.

Extracted from watchdog.py. Each function is a deterministic SQL query
against the canonical pipeline tables (job1_enrichment + frozen_lineups)
returning WatchdogEvent hits for run_watchdog to persist. See
watchdog.py's module docstring for the full trigger catalogue.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from sqlalchemy import text

from wnba_oracle.common.logging import get_logger
from wnba_oracle.common.paths import resolve_project_root
from wnba_oracle.db.engine import get_engine
from wnba_oracle.scheduler.watchdog import (
    SEVERITY_CRITICAL,
    SEVERITY_ERROR,
    SEVERITY_WARN,
    WatchdogEvent,
)

REPO_ROOT = resolve_project_root(__file__)

log = get_logger("oracle.watchdog")

# Per-check SQL kept here (not embedded in the run loop) for grep-ability.

POOL_SIZE_Q = text(
    "SELECT COUNT(*)::int AS n, COUNT(DISTINCT team)::int AS n_teams, "
    "MAX(captured_at) AS last_captured "
    "FROM job1_enrichment WHERE slate_date = :sd"
)

FROZEN_Q = text(
    "SELECT lineup, expected_payout, frozen_at "
    "FROM frozen_lineups "
    "WHERE slate_date = :sd "
    "ORDER BY frozen_at DESC, id DESC LIMIT 1"
)


def _check_pool(slate_date: str) -> list[WatchdogEvent]:
    eng = get_engine()
    with eng.connect() as conn:
        row = conn.execute(POOL_SIZE_Q, {"sd": slate_date}).first()
    n = int(row[0]) if row and row[0] is not None else 0
    n_teams = int(row[1]) if row and row[1] is not None else 0
    if n == 0:
        return [
            WatchdogEvent(
                slate_date=slate_date,
                trigger="no_job1_pool",
                severity=SEVERITY_CRITICAL,
                payload={"pool_size": 0},
            )
        ]
    out: list[WatchdogEvent] = []
    if n < 10:
        # D84: escalated from warn. A sub-10 pool means the ingest
        # partially failed and the tip-relative (T-40) freeze would optimize over a
        # broken universe (the 2026-06-08 incident shape).
        out.append(
            WatchdogEvent(
                slate_date=slate_date,
                trigger="pool_too_small",
                severity=SEVERITY_ERROR,
                payload={"pool_size": n, "threshold": 10},
            )
        )
    if n_teams < 2:
        # Rows exist but from a single team: a degenerate capture that a
        # raw row count can miss. No valid slate has one team.
        out.append(
            WatchdogEvent(
                slate_date=slate_date,
                trigger="pool_degenerate_teams",
                severity=SEVERITY_CRITICAL,
                payload={"pool_size": n, "n_teams": n_teams},
            )
        )
    return out


def _check_enrichment_freshness(
    slate_date: str, *, now_utc: dt.datetime | None = None
) -> list[WatchdogEvent]:
    """D84: warn when the slate's enrichment is stale near freeze time.

    After 20:00 UTC (an hour before the legacy 21:00 evening freeze) the
    newest job1_enrichment capture should be from today's 13:00 UTC fire or
    later. An older capture means job1 silently never refreshed and job2
    is about to freeze on yesterday's universe.

    The 20:00 UTC gate assumes an evening slate. An early tip-off (first
    tip before ~17:00 UTC, D93 tip-relative freeze) already froze hours
    before this check ever runs, on whatever was fresh at that time --
    checking against a fixed 13:30 UTC floor at 20:00 UTC is a guaranteed
    false positive for those slates. Skip once a lineup is already frozen;
    the freeze already happened on today's universe by definition.
    """
    now_utc = now_utc or dt.datetime.now(dt.UTC)
    if now_utc.strftime("%Y-%m-%d") != slate_date or now_utc.hour < 20:
        return []
    eng = get_engine()
    with eng.connect() as conn:
        if conn.execute(FROZEN_Q, {"sd": slate_date}).first() is not None:
            return []
        row = conn.execute(POOL_SIZE_Q, {"sd": slate_date}).first()
    last_captured = row[2] if row else None
    if last_captured is None:
        return []  # no_job1_pool already covers the empty case
    if last_captured.tzinfo is None:
        last_captured = last_captured.replace(tzinfo=dt.UTC)
    fresh_floor = now_utc.replace(hour=13, minute=30, second=0, microsecond=0)
    if last_captured >= fresh_floor:
        return []
    return [
        WatchdogEvent(
            slate_date=slate_date,
            trigger="enrichment_stale",
            severity=SEVERITY_WARN,
            payload={
                "last_captured_utc": last_captured.isoformat(),
                "fresh_floor_utc": fresh_floor.isoformat(),
            },
        )
    ]


# Coverage universe: players referenced by the captured top-20 leaderboard
# lineups. They provably participated in the contest, so a missing label is
# always an ingestion gap, never noise. The job1_enrichment pool cannot be
# the universe -- it is structurally ~3x wider than contest label coverage
# (pool ~90 vs labels ~30 on a 3-game slate), so comparing against it fired
# a false ERROR on every healthy day. slate_date is VARCHAR on both tables
# here; cast the shared :sd param explicitly so Postgres types it.
LABEL_COVERAGE_Q = text(
    """
    WITH lb_players AS (
        SELECT DISTINCT (p->>'playerId')::int AS pid
        FROM contest_leaderboards cl,
             jsonb_array_elements(cl.lineup) p
        WHERE cl.slate_date = CAST(:sd AS varchar)
    )
    SELECT
        (SELECT COUNT(*)::int FROM lb_players) AS n_contest,
        (SELECT COUNT(*)::int FROM lb_players lp
         WHERE NOT EXISTS (
             SELECT 1 FROM slate_labels l
             WHERE l.slate_date = CAST(:sd AS varchar)
               AND l.platform_player_id = lp.pid
         )) AS n_missing
    """
)

LABEL_MISSING_SAMPLE_Q = text(
    """
    SELECT DISTINCT (p->>'playerId')::int AS pid,
           MAX(p->>'displayName') AS name
    FROM contest_leaderboards cl,
         jsonb_array_elements(cl.lineup) p
    WHERE cl.slate_date = CAST(:sd AS varchar)
      AND NOT EXISTS (
          SELECT 1 FROM slate_labels l
          WHERE l.slate_date = CAST(:sd AS varchar)
            AND l.platform_player_id = (p->>'playerId')::int
      )
    GROUP BY (p->>'playerId')::int
    ORDER BY pid
    LIMIT 10
    """
)


def _check_label_coverage(slate_date: str) -> list[WatchdogEvent]:
    """D85: contest players missing from slate_labels lose training labels
    permanently (the Loyd/Boston gap on 2026-06-08).

    Compares the players referenced by the captured top-20 leaderboard
    lineups against slate_labels after dayclose finalizes the contest.
    Any gap in that set is a real ingestion failure: error above 20%
    missing, warn on any gap. Called from the dayclose path, not the cron
    loop: labels and leaderboards only exist after contest finalization.
    """
    eng = get_engine()
    with eng.connect() as conn:
        row = conn.execute(LABEL_COVERAGE_Q, {"sd": slate_date}).first()
        n_contest = int(row[0]) if row and row[0] is not None else 0
        n_missing = int(row[1]) if row and row[1] is not None else 0
        if n_contest == 0 or n_missing == 0:
            return []
        sample = [
            {"player_id": int(r[0]), "name": str(r[1])}
            for r in conn.execute(LABEL_MISSING_SAMPLE_Q, {"sd": slate_date})
        ]
    frac = n_missing / n_contest
    return [
        WatchdogEvent(
            slate_date=slate_date,
            trigger="label_coverage_gap",
            severity=SEVERITY_ERROR if frac > 0.20 else SEVERITY_WARN,
            payload={
                "n_contest": n_contest,
                "n_missing": n_missing,
                "missing_frac": round(frac, 3),
                "sample": sample,
            },
        )
    ]


def _slate_freeze_deadline(slate_date: str, settings: object) -> dt.datetime | None:
    """The tip-relative freeze deadline (first_tip - freeze_lead_minutes) for a
    slate, or None when slate_meta has no tip time. Best-effort; a failure
    degrades the freeze check to its static 22:00 UTC fallback."""
    try:
        from wnba_oracle.scheduler.job2 import _freeze_deadline_utc, _load_slate_lock_time

        return _freeze_deadline_utc(_load_slate_lock_time(slate_date), settings)
    except Exception as exc:
        log.warning("watchdog_freeze_deadline_failed", reason=str(exc)[:120])
        return None


def _check_freeze(slate_date: str, *, now_utc: dt.datetime | None = None) -> list[WatchdogEvent]:
    now_utc = now_utc or dt.datetime.now(dt.UTC)
    eng = get_engine()
    with eng.connect() as conn:
        row = conn.execute(FROZEN_Q, {"sd": slate_date}).first()
    out: list[WatchdogEvent] = []
    if row is None:
        # E: escalate relative to the slate's own tip. A static 22:00 UTC
        # threshold is blind to afternoon slates that lock before the evening
        # cron window -- those would miss the freeze entirely and stay silent
        # until 22:00. When slate_meta carries a first-tip, fire CRITICAL once
        # we pass first_tip - freeze_lead_minutes; otherwise fall back to the
        # legacy today + 22:00 UTC rule.
        from wnba_oracle.common.settings import get_settings

        deadline = _slate_freeze_deadline(slate_date, get_settings())
        if deadline is not None:
            overdue = now_utc >= deadline
            note = f"no frozen row by tip-relative deadline {deadline.isoformat()}"
        else:
            overdue = now_utc.strftime("%Y-%m-%d") == slate_date and now_utc.hour >= 22
            note = "no frozen row after 22:00 UTC (no tip time captured)"
        if overdue:
            out.append(
                WatchdogEvent(
                    slate_date=slate_date,
                    trigger="no_frozen_lineup",
                    severity=SEVERITY_CRITICAL,
                    payload={
                        "checked_at_utc": now_utc.isoformat(),
                        "freeze_deadline_utc": deadline.isoformat() if deadline else None,
                        "note": note,
                    },
                )
            )
        return out

    lineup_json = row[0]
    if isinstance(lineup_json, str):
        lineup_json = json.loads(lineup_json)
    per_player = lineup_json.get("per_player") if isinstance(lineup_json, dict) else None
    if not per_player or len(per_player) != 5:
        out.append(
            WatchdogEvent(
                slate_date=slate_date,
                trigger="missing_per_player",
                severity=SEVERITY_ERROR,
                payload={"per_player_len": len(per_player) if per_player else 0},
            )
        )

    expected_payout = row[1]
    if expected_payout is not None and float(expected_payout) <= 0.0:
        out.append(
            WatchdogEvent(
                slate_date=slate_date,
                trigger="zero_expected_payout",
                severity=SEVERITY_WARN,
                payload={"expected_payout": float(expected_payout)},
            )
        )
    return out


FEATURE_CONTENT_Q = text(
    "SELECT COUNT(*)::int AS n, "
    "COUNT(*) FILTER (WHERE (features_json->>'vegas_total')::float8 > 0)::int AS n_odds, "
    "COUNT(*) FILTER (WHERE (features_json->>'is_starter')::int = 1)::int AS n_starter "
    "FROM job1_enrichment WHERE slate_date = :sd"
)


def _check_model_artifact(
    slate_date: str,
    *,
    model_sha: str | None = None,
    models_dir: Path | None = None,
) -> list[WatchdogEvent]:
    """Critical if the trained model won't load -- the system would silently
    fall back to the boost heuristic (walk-forward corr 0.554 -> 0.246) with no
    other alert. Catches the catastrophic case where WNBA_ORACLE_MODEL_ARTIFACT_SHA
    is wiped/reset or points at a `.pkl` not shipped in the image.
    """
    if model_sha is None:
        from wnba_oracle.common.settings import get_settings

        model_sha = get_settings().model_artifact_sha
    sha = (model_sha or "").strip().lower()
    if not sha:
        return [
            WatchdogEvent(
                slate_date=slate_date,
                trigger="model_artifact_unset",
                severity=SEVERITY_CRITICAL,
                payload={"note": "WNBA_ORACLE_MODEL_ARTIFACT_SHA empty; serving heuristic"},
            )
        ]
    mdir = models_dir or (REPO_ROOT / "models")
    resolved = False
    if mdir.exists():
        for sidecar in mdir.glob("picker_*.sha256"):
            try:
                if sidecar.read_text().strip().lower() != sha:
                    continue
                artifact_path = sidecar.with_suffix(".pkl")
                if not artifact_path.exists():
                    continue
                # ``load_artifact`` verifies the bytes against the sidecar
                # before unpickling. A matching text file alone is not proof
                # that the shipped artifact is readable or safe to serve.
                from wnba_oracle.train.pipeline import PickerArtifact, load_artifact

                artifact = load_artifact(artifact_path)
                if not isinstance(artifact, PickerArtifact):
                    continue
                resolved = True
                break
            except Exception:
                continue
    if not resolved:
        return [
            WatchdogEvent(
                slate_date=slate_date,
                trigger="model_artifact_unresolved",
                severity=SEVERITY_CRITICAL,
                payload={
                    "sha": sha[:12],
                    "note": "artifact missing, checksum-invalid, or unloadable; serving heuristic",
                },
            )
        ]
    return []


def _check_feature_content(slate_date: str) -> list[WatchdogEvent]:
    """Warn when the pool is full but a whole upstream feed is empty -- the
    silent-degradation class the row-count checks miss (D100 shape). Empty odds
    drops the game-script tilt; zero RotoWire starters means lineups never
    parsed/joined (the confirmed-starter signal is dark)."""
    eng = get_engine()
    with eng.connect() as conn:
        row = conn.execute(FEATURE_CONTENT_Q, {"sd": slate_date}).first()
    n = int(row[0]) if row and row[0] is not None else 0
    if n < 10:
        return []  # tiny/empty pool is the _check_pool checks' job, not this.
    n_odds = int(row[1]) if row and row[1] is not None else 0
    n_starter = int(row[2]) if row and row[2] is not None else 0
    out: list[WatchdogEvent] = []
    if n_odds == 0:
        out.append(
            WatchdogEvent(
                slate_date=slate_date,
                trigger="odds_empty",
                severity=SEVERITY_WARN,
                payload={"pool": n, "note": "no vegas_total on any row; game-script tilt off"},
            )
        )
    if n_starter == 0:
        out.append(
            WatchdogEvent(
                slate_date=slate_date,
                trigger="rotowire_empty",
                severity=SEVERITY_WARN,
                payload={"pool": n, "note": "no is_starter flags; RotoWire scrape/join failed"},
            )
        )
    return out


ENRICHMENT_SOURCE_Q = text(
    """
    SELECT COUNT(*)::int AS n_total,
           COUNT(*) FILTER (
           WHERE features_json ? 'vegas_total'
           OR features_json ? 'minutes_l5'
           OR features_json ? 'is_starter'
       )::int AS n_live_enriched
    FROM job1_enrichment WHERE slate_date = :sd
    """
)


def _check_enrichment_source(slate_date: str) -> list[WatchdogEvent]:
    """D107 (#33): detect if enrichment was produced by --job backfill instead of
    live job1. Backfill fills only player_id/name/team, skipping vegas, rotowire,
    and minutes features. If rows exist but NONE have live-enrichment fields
    (vegas_total, minutes_l5, is_starter), the pool is useless and job2 will
    freeze on empty/heuristic data.
    """
    eng = get_engine()
    with eng.connect() as conn:
        row = conn.execute(ENRICHMENT_SOURCE_Q, {"sd": slate_date}).first()
    n_total = int(row[0]) if row and row[0] is not None else 0
    n_live = int(row[1]) if row and row[1] is not None else 0
    if n_total < 10:
        return []  # tiny/empty pool is the _check_pool checks' job
    if n_live == 0:
        # All rows exist but with zero live enrichment fields: backfill-produced
        return [
            WatchdogEvent(
                slate_date=slate_date,
                trigger="enrichment_from_backfill",
                severity=SEVERITY_CRITICAL,
                payload={
                    "n_rows": n_total,
                    "note": "no vegas/rotowire/minutes fields; cron--job backfill was run instead of live job1",
                },
            )
        ]
    return []


def _check_config_drift(slate_date: str, *, settings: object | None = None) -> list[WatchdogEvent]:
    """Warn when the live serving config has drifted from the validated prod
    values (e.g. an env wipe reverted a tuned knob to its safe-off default).
    Non-fatal: a drift may be intentional, but it must not be silent."""
    if settings is None:
        from wnba_oracle.common.settings import get_settings

        settings = get_settings()
    drift = settings.config_drift()  # type: ignore[attr-defined]
    if not drift:
        return []
    return [
        WatchdogEvent(
            slate_date=slate_date,
            trigger="config_drift",
            severity=SEVERITY_WARN,
            payload={"drift": {name: {"actual": a, "expected": e} for name, a, e in drift}},
        )
    ]
