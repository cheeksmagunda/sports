#!/usr/bin/env python3
"""Validate that a built runtime image enforces its configured cron role."""

from __future__ import annotations

import argparse
import os

from oracle_core.jobs import RoleMismatchError, validate_role

from wnba_oracle.common.settings import Settings
from wnba_oracle.scheduler.job_runtime import build_job_registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    args = parser.parse_args()

    role = os.environ.get("WNBA_CRON_ROLE", "").strip()
    if not role:
        parser.error("WNBA_CRON_ROLE is required")
    try:
        validate_role(build_job_registry(Settings()).get(args.job), role)
    except (KeyError, RoleMismatchError) as exc:
        parser.error(str(exc))
    print(f"runtime role accepted: job={args.job} role={role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
