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
  3. When DATABASE_URL is set, the labels + leaderboards are written to
     Postgres (the canonical store). Parquet partitions under
     `data/historical/` are also refreshed if `WNBA_CORPUS_PARQUET_DIR`
     is set (otherwise skipped — parquet is the off-Railway analysis
     surface, not load-bearing for serving).

Cron schedule: `0 6 * * *` UTC = 01:00 EST / 02:00 EDT = ~1h after the
latest plausible WNBA contest finalization. Contest 1831 (slate
2026-05-25) was processedAt 2026-05-26T05:07Z, so 06:00 UTC is the
earliest fire time that always catches the prior night.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from wnba_oracle.common.logging import get_logger
from wnba_oracle.common.settings import get_settings
from wnba_oracle.ingest.backfill import run_historical_backfill
from wnba_oracle.ingest.realsports import discover_wnba_contest_id

log = get_logger("oracle.dayclose")

DEFAULT_WALK_WINDOW = 12  # cover yesterday + the prior day's residue


def main() -> int:
    settings = get_settings()
    parquet_dir_env = os.environ.get("WNBA_CORPUS_PARQUET_DIR", "").strip()
    parquet_dir = Path(parquet_dir_env) if parquet_dir_env else None
    walk_window = int(os.environ.get("WNBA_DAYCLOSE_WALK_WINDOW", DEFAULT_WALK_WINDOW))

    if not settings.database_url and parquet_dir is None:
        log.error(
            "dayclose_no_persistence_target",
            hint=(
                "Set DATABASE_URL or WNBA_CORPUS_PARQUET_DIR; otherwise the "
                "backfill would scrape and discard."
            ),
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
        parquet_dir=str(parquet_dir) if parquet_dir else None,
    )
    return run_historical_backfill(
        start_id=start_id,
        stop_id=stop_id,
        pause_seconds=0.5,
        dry_run=False,
        with_leaderboards=True,
        parquet_out_dir=parquet_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
