"""Scheduled cron entry. Job 1 / Job 2 / dayclose dispatch.

Invoked by Railway's cron with:
  oracle-cron --job job1     # morning enrichment (13:00 UTC)
  oracle-cron --job job1late # credit-free RotoWire confirmed-lineup refresh
                             # (fan across the afternoon/evening; D102/#27)
  oracle-cron --job job1games # backfill per-player game tip times onto tonight's
                             # enrichment (credit-free; D109 pool scope)
  oracle-cron --job job2     # pre-tip optimizer (tip-relative T-40 freeze; cron fires */15 across 14-23,0-3 UTC)
  oracle-cron --job dayclose # corpus extension (06:00 UTC, captures
                             # the prior night's finalized contest)
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import get_settings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--job",
        required=True,
        choices=["job1", "job1games", "job1late", "job2", "dayclose", "backfill"],
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("oracle.cron")

    # D107: cron-role self-check (#33). Prevents D103-style silent misconfigurations
    # where a cron service's start command was overwritten to the wrong --job.
    # Each Railway service sets WNBA_CRON_ROLE to its intended role. If the CLI
    # --job does not match, abort immediately with a critical log.
    intended_role = os.environ.get("WNBA_CRON_ROLE", "").strip()
    if intended_role and args.job != intended_role:
        log.critical(
            "cron_role_mismatch_abort",
            expected_role=intended_role,
            actual_job=args.job,
            msg="WNBA_CRON_ROLE env var does not match --job CLI arg; aborting to prevent silent misconfiguration",
        )
        return 1

    log.info(
        "cron_dispatch",
        job=args.job,
        role=intended_role or "(unchecked)",
        env=settings.env,
        has_database_url=bool(settings.database_url),
        has_redis_url=bool(settings.redis_url),
        has_realsports_creds=bool(settings.real_sports_username and settings.real_sports_password),
    )

    # Operator-directed pause of the picking pipeline (PICKS_PAUSE_START/END).
    # job1/job1late/job2 no-op; dayclose/backfill keep the corpus current.
    # UTC-explicit: cron schedules are all UTC (see AGENTS.md), and a naive
    # dt.date.today() depends on the container's local TZ, which can disagree
    # with the UTC calendar day by hours (see api/watchdog_router.py, which
    # uses the same UTC-explicit pattern for the same reason).
    today_utc = dt.datetime.now(dt.UTC).date()
    if args.job in ("job1", "job1games", "job1late", "job2") and settings.picks_paused_on(
        today_utc
    ):
        log.info(
            "picks_paused_skip",
            job=args.job,
            pause_start=settings.picks_pause_start,
            pause_end=settings.picks_pause_end,
        )
        return 0

    if args.job == "job1":
        from wnba_oracle.scheduler import job1
        from wnba_oracle.scheduler.watchdog import run_watchdog

        rc = job1.main()
        # D84: run the watchdog after job1 too, so a degraded or absent
        # morning pool pages at 13:00 UTC instead of being discovered by
        # the job2 freeze fire (or the operator's screenshot). Wrapped so a
        # watchdog crash never masks job1's exit code.
        try:
            # config_drift describes cron-job2's env only; job1's process
            # never has those knobs set, so skip it here (see run_watchdog).
            run_watchdog(dt.date.today().isoformat(), check_config_drift=False)
        except Exception as exc:
            log.exception("watchdog_failed", error=str(exc))
        return rc
    if args.job == "job1games":
        # D109: refresh features_json["game_start_utc"] without a full job1.
        # On a Railway cron the D107 role guard applies, so this needs
        # WNBA_CRON_ROLE=job1games (or unset) on the service that runs it.
        from wnba_oracle.scheduler import job1

        job1.run_game_starts(dt.datetime.now(dt.UTC).date().isoformat())
        return 0
    if args.job == "job1late":
        # Credit-free confirmed-lineup refresh. Re-scrapes
        # RotoWire and JSONB-merges only the starter/confirmed fields onto the
        # existing enrichment, so afternoon slates pick up confirmed starters
        # before their T-40 freeze without burning Odds API credits. No watchdog
        # (this is a targeted refresh, not a freeze).
        from wnba_oracle.scheduler import job1

        return job1.main_lite()
    if args.job == "job2":
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
