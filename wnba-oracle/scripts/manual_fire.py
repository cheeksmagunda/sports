"""End-to-end manual fire against the live Real Sports slate.

Steps:
1. Job 1 (live data): pool + odds + lineups -> persisted enrichment.
2. Job 2 (live data): picker -> frozen lineup.
3. Watchdog: post-Job-2 trigger evaluation.

Usage:
    set -a && source .env && set +a
    uv run python scripts/manual_fire.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

from wnba_oracle.common.logging import configure_logging, get_logger

log = get_logger("oracle.manual_fire")


def _ensure_db_available() -> bool:
    from wnba_oracle.common.settings import get_settings

    s = get_settings()
    if not s.database_url:
        print(
            "[skip] DATABASE_URL not set; manual_fire does not persist when DB is offline.",
            file=sys.stderr,
        )
        return False
    return True


def _run_live_fire(slate_date: str) -> int:
    from wnba_oracle.scheduler.job1 import run as run_job1
    from wnba_oracle.scheduler.job2 import run as run_job2
    from wnba_oracle.scheduler.watchdog import run_watchdog

    j1 = run_job1(slate_date)
    print(json.dumps({"job1": j1.__dict__}, indent=2, default=str))
    j2 = run_job2(slate_date)
    print(
        json.dumps(
            {
                "job2": {
                    "slate_date": j2.slate_date,
                    "model_sha": j2.model_sha,
                    "frozen": j2.frozen,
                    "reason": j2.reason,
                    "recommendation_player_ids": list(j2.recommendation.player_ids)
                    if j2.recommendation
                    else None,
                    "expected_payout": j2.recommendation.expected_payout
                    if j2.recommendation
                    else None,
                    "entry_flag": j2.recommendation.entry_flag if j2.recommendation else None,
                }
            },
            indent=2,
            default=str,
        )
    )
    events = run_watchdog(slate_date)
    print(json.dumps({"watchdog": {"events": len(events)}}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=dt.date.today().isoformat())
    args = parser.parse_args()
    configure_logging("INFO")

    if not _ensure_db_available():
        return 1
    return _run_live_fire(args.date)


if __name__ == "__main__":
    sys.exit(main())
