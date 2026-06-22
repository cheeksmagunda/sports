"""Scheduled cron entry. Job 1 / Job 2 / dayclose dispatch.

Invoked by Railway's cron with:
  oracle-cron --job job1     # morning enrichment (13:00 UTC)
  oracle-cron --job job1late # credit-free RotoWire confirmed-lineup refresh
                             # (fan across the afternoon/evening; D102/#27)
  oracle-cron --job job2     # pre-tip optimizer (tip-relative T-40 freeze; cron fires */15 across 14-23,0-3 UTC)
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
        "--job",
        required=True,
        choices=["job1", "job1late", "job2", "dayclose", "backfill"],
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
        import datetime as dt

        from wnba_oracle.scheduler import job1
        from wnba_oracle.scheduler.watchdog import run_watchdog

        rc = job1.main()
        # D84: run the watchdog after job1 too, so a degraded or absent
        # morning pool pages at 13:00 UTC instead of being discovered by
        # the job2 freeze fire (or the operator's screenshot). Wrapped so a
        # watchdog crash never masks job1's exit code.
        try:
            run_watchdog(dt.date.today().isoformat())
        except Exception as exc:
            log.exception("watchdog_failed", error=str(exc))
        return rc
    if args.job == "job1late":
        # D102 (NEEDS_CLAUDE #27): credit-free confirmed-lineup refresh. Re-scrapes
        # RotoWire and JSONB-merges only the starter/confirmed fields onto the
        # existing enrichment, so afternoon slates pick up confirmed starters
        # before their T-40 freeze without burning Odds API credits. No watchdog
        # (this is a targeted refresh, not a freeze).
        from wnba_oracle.scheduler import job1

        return job1.main_lite()
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
    if args.job == "backfill":
        from wnba_oracle.scheduler import job_backfill

        return job_backfill.main()
    return 1


if __name__ == "__main__":
    sys.exit(main())
