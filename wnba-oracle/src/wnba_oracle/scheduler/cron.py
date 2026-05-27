"""Scheduled cron entry. Job 1 / Job 2 dispatch.

Invoked by Railway's cron with:
  oracle-cron --job job1
  oracle-cron --job job2

Full Job 1 / Job 2 implementations land in Step 8 of the build plan. Until
then this dispatcher logs the requested job, performs the credential probe,
and exits 0 so cron fires are observable without crashing.
"""

from __future__ import annotations

import argparse
import sys

from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import get_settings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True, choices=["job1", "job2"])
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
        from wnba_oracle.scheduler import job2

        return job2.main()
    return 1


if __name__ == "__main__":
    sys.exit(main())
