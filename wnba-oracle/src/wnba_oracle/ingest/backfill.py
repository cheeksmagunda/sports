"""WNBA contest backfill + corpus assembler.

Two flows:

1. **Live collector** (`run_live_collect`): once per day, after the
   active WNBA contest finalizes (~midnight ET), fetch /stats and persist
   per-player labels to `slate_labels` in Postgres.

2. **Historical backfill** (`run_historical_backfill`): scan past contest
   ids and try to fetch each. The Real Sports platform restricts most
   past contests to "my draft attempts" - we keep whatever returns 200.
   Logs the success rate so the operator can see how many slates we
   could recover.

Operator entry: `oracle-backfill --mode {live|historical} [--start-id N]`.

Persistence: `slate_labels` table (added in migration
20260527_0002_slate_labels). One row per (contest_id, platform_player_id).
`real_score` is the training label.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import sqlalchemy as sa
from sqlalchemy import create_engine, text

from wnba_oracle.common.db_utils import normalize_postgres_url
from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import get_settings
from wnba_oracle.ingest.contest_stats import (
    ContestLabel,
    ContestUnavailable,
    dedupe_by_player,
    fetch_contest_stats,
)
from wnba_oracle.ingest.realsports import (
    PlatformAuthRequired,
    discover_wnba_contest_id,
    headers_or_capture,
)

log = get_logger("oracle.ingest.backfill")


def _engine() -> sa.Engine:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL not set; cannot persist labels.")
    return create_engine(
        normalize_postgres_url(settings.database_url),
        future=True,
        pool_pre_ping=True,
    )


UPSERT_SQL = text(
    """
    INSERT INTO slate_labels (
        contest_id, slate_date, section, platform_player_id, display_name,
        team_key, card_boost, drafts, real_score, ingested_at
    )
    VALUES (
        :contest_id, :slate_date, :section, :platform_player_id, :display_name,
        :team_key, :card_boost, :drafts, :real_score, now()
    )
    ON CONFLICT (contest_id, platform_player_id) DO UPDATE SET
        card_boost = EXCLUDED.card_boost,
        real_score = EXCLUDED.real_score,
        drafts = EXCLUDED.drafts,
        section = EXCLUDED.section,
        ingested_at = now();
    """
)


def persist_labels(labels: list[ContestLabel]) -> int:
    if not labels:
        return 0
    engine = _engine()
    n = 0
    with engine.begin() as conn:
        for label in dedupe_by_player(labels):
            conn.execute(UPSERT_SQL, label.__dict__)
            n += 1
    return n


def _iter_contest_ids(start: int, stop: int) -> Iterator[int]:
    if start <= stop:
        yield from range(start, stop + 1)
    else:
        yield from range(start, stop - 1, -1)


def _force_reauth(device_uuid: str, device_name: str):
    """Drop the cached token file and force a Playwright re-capture.
    Returned closure matches `Callable[[], RequestHeaders]`."""
    from wnba_oracle.ingest.realsports import TOKEN_CACHE_PATH, capture_live_headers

    def _do_refresh():
        if Path(TOKEN_CACHE_PATH).exists():
            Path(TOKEN_CACHE_PATH).unlink(missing_ok=True)
        return asyncio.run(capture_live_headers(device_uuid, device_name))

    return _do_refresh


def run_live_collect(*, dry_run: bool = False) -> int:
    """Fetch the currently active WNBA contest's stats and persist."""
    device_uuid = os.environ.get("WNBA_DEVICE_UUID", "")
    device_name = os.environ.get("WNBA_DEVICE_NAME", "wnba-oracle-prod-01")
    if not device_uuid:
        log.error("missing WNBA_DEVICE_UUID env var; cannot reauth")
        return 1

    headers = asyncio.run(headers_or_capture(device_uuid, device_name))
    contest_id = asyncio.run(discover_wnba_contest_id())
    if contest_id is None:
        log.warning("no_active_wnba_contest_id")
        return 0

    refresh = _force_reauth(device_uuid, device_name)
    with httpx.Client(timeout=20.0) as client:
        try:
            labels = fetch_contest_stats(
                contest_id, headers, client, refresh_headers=refresh
            )
        except ContestUnavailable as exc:
            log.warning("contest_unavailable", contest_id=contest_id, reason=str(exc))
            return 0

    log.info(
        "live_collect_done",
        contest_id=contest_id,
        n_rows=len(labels),
        with_real_score=sum(1 for label in labels if label.real_score is not None),
    )
    if dry_run:
        return 0
    n = persist_labels(labels)
    log.info("live_collect_persisted", n=n)
    return 0


def run_historical_backfill(
    *,
    start_id: int,
    stop_id: int,
    pause_seconds: float = 1.0,
    dry_run: bool = False,
) -> int:
    """Walk a contest-id range, persist whatever returns 200 and sport=wnba."""
    device_uuid = os.environ.get("WNBA_DEVICE_UUID", "")
    device_name = os.environ.get("WNBA_DEVICE_NAME", "wnba-oracle-backfill-01")
    if not device_uuid:
        log.error("missing WNBA_DEVICE_UUID env var; cannot reauth")
        return 1

    headers = asyncio.run(headers_or_capture(device_uuid, device_name))
    refresh = _force_reauth(device_uuid, device_name)
    n_success = 0
    n_unavailable = 0
    n_auth_failed = 0
    with httpx.Client(timeout=20.0) as client:
        for cid in _iter_contest_ids(start_id, stop_id):
            try:
                labels = fetch_contest_stats(
                    cid, headers, client, refresh_headers=refresh
                )
            except ContestUnavailable as exc:
                log.info("skip", contest_id=cid, reason=str(exc))
                n_unavailable += 1
                time.sleep(pause_seconds)
                continue
            except PlatformAuthRequired:
                log.warning("auth_required", contest_id=cid)
                n_auth_failed += 1
                time.sleep(pause_seconds)
                continue
            if not labels:
                n_unavailable += 1
                time.sleep(pause_seconds)
                continue
            if not dry_run:
                persist_labels(labels)
            n_success += 1
            log.info("kept", contest_id=cid, n_rows=len(labels))
            time.sleep(pause_seconds)

    log.info(
        "historical_backfill_done",
        n_success=n_success,
        n_unavailable=n_unavailable,
        n_auth_failed=n_auth_failed,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["live", "historical"], required=True)
    parser.add_argument("--start-id", type=int, help="historical start contest id")
    parser.add_argument("--stop-id", type=int, help="historical stop contest id")
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    configure_logging("INFO")

    if args.mode == "live":
        return run_live_collect(dry_run=args.dry_run)
    if args.mode == "historical":
        if args.start_id is None or args.stop_id is None:
            print("--start-id and --stop-id required for historical mode", file=sys.stderr)
            return 2
        return run_historical_backfill(
            start_id=args.start_id,
            stop_id=args.stop_id,
            pause_seconds=args.pause_seconds,
            dry_run=args.dry_run,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
