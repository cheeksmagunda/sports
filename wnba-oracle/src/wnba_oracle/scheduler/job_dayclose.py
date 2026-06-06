"""Day-close cron: capture yesterday's finalized WNBA contest and extend
the historical corpus by one slate.

Pipeline:
  1. Playwright-sniff the freshest contest id via discover_wnba_contest_id
     (cron container picks up the absolute max id across all sports; the
     downstream sport filter in fetch_contest_stats rejects non-WNBA ids).
  2. Walk backward from (max_id - 1) over a small bounded window, calling
     the existing historical backfill. The UPSERT semantics on
     slate_labels / contest_leaderboards mean re-processing an already-
     captured contest is a cheap no-op, so the window can overlap day-
     to-day without drift.
  3. Labels + leaderboards are written to Postgres (the canonical store).

Cron schedule: `0 6 * * *` UTC = 01:00 EST / 02:00 EDT = ~1h after the
latest plausible WNBA contest finalization. Contest 1831 (slate
2026-05-25) was processedAt 2026-05-26T05:07Z, so 06:00 UTC is the
earliest fire time that always catches the prior night.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os

from wnba_oracle.common.logging import get_logger
from wnba_oracle.common.settings import get_settings
from wnba_oracle.ingest.backfill import run_historical_backfill
from wnba_oracle.ingest.realsports import discover_wnba_contest_id

log = get_logger("oracle.dayclose")

DEFAULT_WALK_WINDOW = 12  # cover yesterday + the prior day's residue


def main() -> int:
    settings = get_settings()
    walk_window = int(os.environ.get("WNBA_DAYCLOSE_WALK_WINDOW", DEFAULT_WALK_WINDOW))

    if not settings.database_url:
        log.error(
            "dayclose_no_persistence_target",
            hint="Set DATABASE_URL; Postgres is the canonical store.",
        )
        return 1

    try:
        top_cid = asyncio.run(discover_wnba_contest_id())
    except Exception as exc:
        log.exception("dayclose_discover_failed", error=str(exc))
        return 1
    if top_cid is None:
        log.warning("dayclose_no_contest_id")
        return 0

    start_id = top_cid - 1
    stop_id = max(1, top_cid - walk_window)
    log.info(
        "dayclose_walk",
        top_cid=top_cid,
        start_id=start_id,
        stop_id=stop_id,
    )
    rc = run_historical_backfill(
        start_id=start_id,
        stop_id=stop_id,
        pause_seconds=0.5,
        dry_run=False,
        with_leaderboards=True,
    )

    # Best-effort: refresh the RESULTS.md ledger for the slate that just
    # finalized (yesterday UTC). Guarded by WNBA_RESULTS_LEDGER so the
    # default Railway fire is a clean no-op — the cron container's repo is
    # ephemeral, so the write only matters when the env var points at a
    # persisted / committed path (operator host or a future GH Action).
    # A ledger failure never changes the dayclose exit code. See D66.
    ledger_env = os.environ.get("WNBA_RESULTS_LEDGER", "").strip()
    if ledger_env:
        from wnba_oracle.scheduler import results_ledger

        yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        try:
            results_ledger.append_for_slate(yesterday, Path(ledger_env))
        except Exception as exc:
            log.exception("dayclose_results_append_failed", error=str(exc))

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
