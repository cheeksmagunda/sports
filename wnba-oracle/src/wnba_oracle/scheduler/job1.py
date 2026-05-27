"""Job 1: morning scrape + Real Sports re-auth + odds + RotoWire lineups.

Full implementation lands in Step 8. This stub keeps the cron fire path
observable and exits cleanly when invoked.
"""

from __future__ import annotations

from wnba_oracle.common.logging import get_logger

log = get_logger("oracle.job1")


def main() -> int:
    log.warning(
        "job1_stub", message="Job 1 implementation pending Step 8; exiting cleanly."
    )
    return 0
