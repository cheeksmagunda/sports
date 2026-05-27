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
- ``pool_too_small`` (warn) — fewer than 10 enrichment rows (a normal
  WNBA slate has 60+ players). Indicates an ingest partial failure.
- ``no_frozen_lineup`` (critical) — after 22:00 UTC there's still no
  frozen row. cron-job2 has had at least 4 attempts (21:00, 21:15,
  21:30, 21:45) and failed every one. Manual fire likely needed.
- ``missing_per_player`` (error) — frozen JSONB lacks the per_player
  block. The frontend will render placeholder cards. Should be
  impossible after D36, but the check is cheap and protects against
  future regressions.
- ``zero_expected_payout`` (warn) — lineup frozen with
  ``expected_payout = 0``. Optimizer either returned a degenerate
  solution or the payout curve was misconfigured. Operator should
  skip the contest.

Each trigger writes at most once per (slate_date, trigger) tuple per
run to avoid log spam; persistence dedup is enforced by querying for
an existing row before INSERT.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field

from sqlalchemy import text

from wnba_oracle.common.logging import get_logger
from wnba_oracle.db.engine import get_engine

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
    "SELECT COUNT(*)::int AS n FROM job1_enrichment WHERE slate_date = :sd"
)

FROZEN_Q = text(
    "SELECT lineup, expected_payout, frozen_at "
    "FROM frozen_lineups "
    "WHERE slate_date = :sd "
    "ORDER BY frozen_at DESC LIMIT 1"
)


def _check_pool(slate_date: str) -> list[WatchdogEvent]:
    eng = get_engine()
    with eng.connect() as conn:
        row = conn.execute(POOL_SIZE_Q, {"sd": slate_date}).first()
    n = int(row[0]) if row else 0
    if n == 0:
        return [
            WatchdogEvent(
                slate_date=slate_date,
                trigger="no_job1_pool",
                severity=SEVERITY_CRITICAL,
                payload={"pool_size": 0},
            )
        ]
    if n < 10:
        return [
            WatchdogEvent(
                slate_date=slate_date,
                trigger="pool_too_small",
                severity=SEVERITY_WARN,
                payload={"pool_size": n, "threshold": 10},
            )
        ]
    return []


def _check_freeze(slate_date: str, *, now_utc: dt.datetime | None = None) -> list[WatchdogEvent]:
    now_utc = now_utc or dt.datetime.now(dt.UTC)
    eng = get_engine()
    with eng.connect() as conn:
        row = conn.execute(FROZEN_Q, {"sd": slate_date}).first()
    out: list[WatchdogEvent] = []
    if row is None:
        # cron-job2 schedule fires at 21:00, 21:15, 21:30, 21:45 UTC; by
        # 22:00 UTC at least one fire should have succeeded. Critical
        # signal if the slate is the current UTC date and we're past
        # 22:00.
        if now_utc.strftime("%Y-%m-%d") == slate_date and now_utc.hour >= 22:
            out.append(
                WatchdogEvent(
                    slate_date=slate_date,
                    trigger="no_frozen_lineup",
                    severity=SEVERITY_CRITICAL,
                    payload={
                        "checked_at_utc": now_utc.isoformat(),
                        "note": "no frozen row after 22:00 UTC",
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
    events.extend(_check_freeze(slate_date, now_utc=now_utc))
    if events:
        persist_events(events)
    else:
        log.info("watchdog_clean", slate_date=slate_date)
    return events
