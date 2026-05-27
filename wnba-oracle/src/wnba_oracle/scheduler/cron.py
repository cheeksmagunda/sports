"""Scheduled cron entry. Job 1 / Job 2 / dayclose dispatch.

Invoked by Railway's cron with:
  oracle-cron --job job1     # morning enrichment (13:00 UTC)
  oracle-cron --job job2     # pre-tip optimizer (21:00 UTC, every 15 min)
  oracle-cron --job dayclose # corpus extension (06:00 UTC, captures
                             # the prior night's finalized contest)
"""

from __future__ import annotations

import argparse
import sys

from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import get_settings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--job", required=True, choices=["job1", "job2", "dayclose"]
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("oracle.cron")

    log.info(
        "cron_dispatch",
        job=args.job,
        env=settings.env,
        has_database_url=bool(settings.database_url),
        has_redis_url=bool(settings.redis_url),
        has_realsports_creds=bool(
            settings.real_sports_username and settings.real_sports_password
        ),
    )

    if args.job == "job1":
        from wnba_oracle.scheduler import job1

        return job1.main()
    if args.job == "job2":
        import datetime as dt

        from wnba_oracle.scheduler import job2
        from wnba_oracle.scheduler.watchdog import run_watchdog

        rc = job2.main()
        # Always run the watchdog, even on job2 failure — the most
        # interesting checks (no_job1_pool, no_frozen_lineup) fire
        # exactly when job2 cannot produce a freeze. Wrap so a watchdog
        # crash never masks the underlying job2 exit code.
        try:
            run_watchdog(dt.date.today().isoformat())
        except Exception as exc:
            log.exception("watchdog_failed", error=str(exc))
        return rc
    if args.job == "dayclose":
        from wnba_oracle.scheduler import job_dayclose

        return job_dayclose.main()
    return 1


if __name__ == "__main__":
    sys.exit(main())
