"""Watchdog: pipeline-health checks + persistence + operator surface.

Each check is a deterministic SQL query against the canonical pipeline
tables (job1_enrichment + frozen_lineups). The checks run after every
cron-job2 fire so the most recent slate is always evaluated. Hits emit
a row into ``watchdog_events`` (severity warn/error/critical), a
structured log line tagged ``watchdog_event``, and surface on the
``/watchdog/today`` API endpoint so the operator can poll from a phone
without log access.

Triggers implemented (post-MVP, expand as the eval bundle grows):

- ``no_job1_pool`` (critical) — slate_date has zero job1_enrichment rows
  by the time the watchdog runs. Either cron-job1 failed or hasn't
  fired. The frontend will keep showing the countdown.
- ``pool_too_small`` (error, escalated from warn in D84) — fewer than 10
  enrichment rows (a normal WNBA slate has 60+ players). Indicates an
  ingest partial failure.
- ``pool_degenerate_teams`` (critical, D84) — enrichment rows exist but
  span fewer than 2 distinct teams. No valid slate has one team; a raw
  row count can miss this shape.
- ``enrichment_stale`` (warn, D84) — after 20:00 UTC the newest capture
  for today's slate predates the 13:00 UTC job1 fire window; job2 is
  about to freeze on yesterday's universe.
- ``no_frozen_lineup`` (critical) — no frozen row by the slate's freeze
  deadline (first_tip - freeze_lead_minutes when slate_meta has a tip,
  else the legacy 22:00 UTC fallback). The tip-relative form catches an
  afternoon slate that would lock before the evening cron window. Manual
  fire likely needed.
- ``missing_per_player`` (error) — frozen JSONB lacks the per_player
  block. The frontend will render placeholder cards. Should be
  impossible after D36, but the check is cheap and protects against
  future regressions.
- ``zero_expected_payout`` (warn) — lineup frozen with
  ``expected_payout = 0``. Optimizer either returned a degenerate
  solution or the payout curve was misconfigured. Operator should
  skip the contest.

Other writers reuse persist_events for out-of-run triggers:
``job1_pool_degraded`` (critical, job1's D84 sanity gate) and
``late_refreeze_gated`` (warn, job2's D83 lock gate).

When WATCHDOG_PING_URL is set, any critical event also fires a
best-effort GET to ``{url}/fail`` (dead-man's-switch paging, D84).

Each trigger writes at most once per (slate_date, trigger) tuple per
run to avoid log spam; persistence dedup is enforced by querying for
an existing row before INSERT.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import text

from wnba_oracle.common.logging import get_logger
from wnba_oracle.db.engine import get_engine

REPO_ROOT = Path(__file__).resolve().parents[3]

log = get_logger("oracle.watchdog")


SEVERITY_WARN = "warn"
SEVERITY_ERROR = "error"
SEVERITY_CRITICAL = "critical"


@dataclass(frozen=True)
class WatchdogEvent:
    slate_date: str
    trigger: str
    severity: str
    payload: dict = field(default_factory=dict)


WATCHDOG_INSERT = text(
    """
    INSERT INTO watchdog_events (
        slate_date, trigger, severity, payload_json, created_at
    ) VALUES (
        :slate_date, :trigger, :severity, CAST(:payload AS JSONB), now()
    )
    """
)

# De-dup: skip inserting a (slate_date, trigger) if one already fired in
# the last 6h. Same hit logged every 15 min from the cron loop would
# otherwise flood watchdog_events.
WATCHDOG_RECENT = text(
    """
    SELECT 1 FROM watchdog_events
    WHERE slate_date = :slate_date AND trigger = :trigger
      AND created_at > now() - INTERVAL '6 hours'
    LIMIT 1
    """
)


def persist_events(events: list[WatchdogEvent]) -> int:
    """Insert events, deduplicating within a 6h window per (slate, trigger)."""
    if not events:
        return 0
    eng = get_engine()
    n = 0
    with eng.begin() as conn:
        for ev in events:
            recent = conn.execute(
                WATCHDOG_RECENT,
                {"slate_date": ev.slate_date, "trigger": ev.trigger},
            ).first()
            if recent:
                log.info(
                    "watchdog_dedup",
                    slate_date=ev.slate_date,
                    trigger=ev.trigger,
                    severity=ev.severity,
                )
                continue
            conn.execute(
                WATCHDOG_INSERT,
                {
                    "slate_date": ev.slate_date,
                    "trigger": ev.trigger,
                    "severity": ev.severity,
                    "payload": json.dumps(ev.payload),
                },
            )
            n += 1
            log.warning(
                "watchdog_event",
                slate_date=ev.slate_date,
                trigger=ev.trigger,
                severity=ev.severity,
                **ev.payload,
            )
    return n


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
    "ORDER BY freeze_seq DESC, frozen_at DESC LIMIT 1"
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

    After 20:00 UTC (an hour before the 21:00 freeze) the newest
    job1_enrichment capture should be from today's 13:00 UTC fire or
    later. An older capture means job1 silently never refreshed and job2
    is about to freeze on yesterday's universe.
    """
    now_utc = now_utc or dt.datetime.now(dt.UTC)
    if now_utc.strftime("%Y-%m-%d") != slate_date or now_utc.hour < 20:
        return []
    eng = get_engine()
    with eng.connect() as conn:
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


LABEL_COVERAGE_Q = text(
    """
    SELECT
        (SELECT COUNT(*)::int FROM job1_enrichment e
         WHERE e.slate_date = :sd) AS n_pool,
        (SELECT COUNT(*)::int FROM job1_enrichment e
         WHERE e.slate_date = :sd
           AND NOT EXISTS (
               SELECT 1 FROM slate_labels l
               WHERE l.slate_date = :sd
                 AND l.platform_player_id = e.player_id
           )) AS n_missing
    """
)

LABEL_MISSING_SAMPLE_Q = text(
    """
    SELECT e.player_id, e.name FROM job1_enrichment e
    WHERE e.slate_date = :sd
      AND NOT EXISTS (
          SELECT 1 FROM slate_labels l
          WHERE l.slate_date = :sd
            AND l.platform_player_id = e.player_id
      )
    ORDER BY e.player_id
    LIMIT 10
    """
)


def _check_label_coverage(slate_date: str) -> list[WatchdogEvent]:
    """D85: pool players missing from slate_labels lose training labels
    permanently (the Loyd/Boston gap on 2026-06-08).

    Compares the slate's job1_enrichment universe against slate_labels
    after dayclose finalizes the contest. Error above 20% missing, warn
    on any gap. Called from the dayclose path, not the cron loop: labels
    only exist after contest finalization.
    """
    eng = get_engine()
    with eng.connect() as conn:
        row = conn.execute(LABEL_COVERAGE_Q, {"sd": slate_date}).first()
        n_pool = int(row[0]) if row and row[0] is not None else 0
        n_missing = int(row[1]) if row and row[1] is not None else 0
        if n_pool == 0 or n_missing == 0:
            return []
        sample = [
            {"player_id": int(r[0]), "name": str(r[1])}
            for r in conn.execute(LABEL_MISSING_SAMPLE_Q, {"sd": slate_date})
        ]
    frac = n_missing / n_pool
    return [
        WatchdogEvent(
            slate_date=slate_date,
            trigger="label_coverage_gap",
            severity=SEVERITY_ERROR if frac > 0.20 else SEVERITY_WARN,
            payload={
                "n_pool": n_pool,
                "n_missing": n_missing,
                "missing_frac": round(frac, 3),
                "sample": sample,
            },
        )
    ]


def _ping_on_critical(events: list[WatchdogEvent]) -> None:
    """D84: best-effort dead-man's-switch ping when anything critical fired.

    GETs {WATCHDOG_PING_URL}/fail so an external monitor (healthchecks.io
    style) pages the operator. Never raises; paging must not break the
    pipeline it watches. No-op until the operator provisions the URL
    (see NEEDS_CLAUDE.md).
    """
    from wnba_oracle.common.settings import get_settings

    url = get_settings().watchdog_ping_url.strip().rstrip("/")
    if not url:
        return
    if not any(ev.severity == SEVERITY_CRITICAL for ev in events):
        return
    try:
        import httpx

        httpx.get(f"{url}/fail", timeout=5.0)
        log.info("watchdog_ping_sent", url_suffix="/fail")
    except Exception as exc:
        log.warning("watchdog_ping_failed", reason=str(exc)[:120])


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
                if sidecar.read_text().strip().lower() == sha and sidecar.with_suffix(".pkl").exists():
                    resolved = True
                    break
            except OSError:
                continue
    if not resolved:
        return [
            WatchdogEvent(
                slate_date=slate_date,
                trigger="model_artifact_unresolved",
                severity=SEVERITY_CRITICAL,
                payload={"sha": sha[:12], "note": "no matching .pkl in models/; serving heuristic"},
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


def run_watchdog(
    slate_date: str, *, now_utc: dt.datetime | None = None
) -> list[WatchdogEvent]:
    """Run all checks for the slate; persist deduplicated events.

    Returns the full event list for caller-side logging / API surface.
    Persistence is idempotent within 6h per (slate, trigger).
    """
    log.info("watchdog_run", slate_date=slate_date)
    events: list[WatchdogEvent] = []
    events.extend(_check_pool(slate_date))
    events.extend(_check_enrichment_freshness(slate_date, now_utc=now_utc))
    events.extend(_check_freeze(slate_date, now_utc=now_utc))
    events.extend(_check_model_artifact(slate_date))
    events.extend(_check_feature_content(slate_date))
    events.extend(_check_config_drift(slate_date))
    if events:
        persist_events(events)
        _ping_on_critical(events)
    else:
        log.info("watchdog_clean", slate_date=slate_date)
    return events
