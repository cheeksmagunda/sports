"""Watchdog: six triggers from Part 7 + persist events to `watchdog_events`.

Each trigger is a simple post-Job-2 check. On hit, writes a row to the
watchdog_events table with severity 'warn' or 'error'. The cron dispatcher
calls `run_watchdog(slate_date)` after Job 2.

Triggers:
- halt_rate                  : > 30% of pool dropped at identity resolution
- per_position_drop          : a cohort (G/F/C) under-represented vs prior
- flat_lineup                : P90 - P10 < 5 points (degenerate distribution)
- realized_value_collapse    : day-close MAE > 2x rolling baseline (post-tip)
- feature_schema_drift       : adversarial validation AUC > 0.6
- p50_mean_shift             : day-over-day P50 mean shift > 4 sigma
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import text

from wnba_oracle.common.logging import get_logger
from wnba_oracle.db.engine import get_engine

log = get_logger("oracle.watchdog")


@dataclass(frozen=True)
class WatchdogEvent:
    slate_date: str
    trigger: str
    severity: str
    payload: dict


WATCHDOG_INSERT = text(
    """
    INSERT INTO watchdog_events (
        slate_date, trigger, severity, payload_json, created_at
    ) VALUES (
        :slate_date, :trigger, :severity, CAST(:payload AS JSONB), now()
    )
    """
)


def persist_events(events: list[WatchdogEvent]) -> int:
    if not events:
        return 0
    eng = get_engine()
    n = 0
    with eng.begin() as conn:
        for ev in events:
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
            log.warning("watchdog_event", trigger=ev.trigger, severity=ev.severity)
    return n


def run_watchdog(slate_date: str) -> list[WatchdogEvent]:
    """Stub: full trigger implementation lands when the post-tip realized
    data is available. For now, logs that the watchdog ran for the slate
    and returns an empty event list.
    """
    log.info("watchdog_run", slate_date=slate_date)
    return []
