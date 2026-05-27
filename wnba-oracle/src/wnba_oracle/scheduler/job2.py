"""Job 2: predict + freeze near tip. Redis SET NX + Postgres UPSERT.

Full implementation lands in Step 8. This stub keeps the cron fire path
observable and exits cleanly when invoked.
"""

from __future__ import annotations

from wnba_oracle.common.logging import get_logger

log = get_logger("oracle.job2")


def main() -> int:
    log.warning(
        "job2_stub", message="Job 2 implementation pending Step 8; exiting cleanly."
    )
    return 0
