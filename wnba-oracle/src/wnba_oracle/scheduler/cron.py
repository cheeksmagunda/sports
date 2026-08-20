"""WNBA cron command backed by the shared job runner."""

from __future__ import annotations

import argparse
import os
import sys

from oracle_core.jobs import JobRunner, RoleMismatchError

from wnba_oracle.common.clock import slate_date as current_slate_date
from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import get_settings
from wnba_oracle.scheduler.job_runtime import (
    JOB_NAMES,
    PostgresJobRunHook,
    WatchdogLifecycleHook,
    build_job_registry,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True, choices=list(JOB_NAMES))
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("oracle.cron")
    intended_role = os.environ.get("WNBA_CRON_ROLE", "").strip()
    role = intended_role or args.job

    log.info(
        "cron_dispatch",
        job=args.job,
        role=intended_role or "(unchecked)",
        env=settings.env,
        has_database_url=bool(settings.database_url),
        has_redis_url=bool(settings.redis_url),
        has_realsports_creds=settings.has_legacy_realsports_credentials,
    )

    runner = JobRunner(
        build_job_registry(settings),
        logger=log,
        hooks=(PostgresJobRunHook(log), WatchdogLifecycleHook(log)),
    )
    try:
        result = runner.run(
            args.job,
            role=role,
            metadata={"slate_date": current_slate_date().isoformat()},
        )
    except RoleMismatchError:
        log.critical(
            "cron_role_mismatch_abort",
            expected_role=intended_role,
            actual_job=args.job,
            msg="WNBA_CRON_ROLE does not match the selected job",
        )
        return 1
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
