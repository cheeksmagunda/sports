"""Job 1: morning scrape + Real Sports re-auth + odds + RotoWire lineups.

Output: job1_enrichment rows in Postgres, one per (slate_date, player_id).
Idempotent: re-running on the same day UPSERTs and overwrites.

Pipeline:
1. Headless re-auth via Playwright (uses scraper/storage_state.json).
2. Real Sports pool fetch (/home/wnba/next + a..z search overlay).
3. The Odds API basketball_wnba pull.
4. RotoWire lineups scrape.
5. Persist enrichment to Postgres.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
from dataclasses import dataclass

import httpx
import sqlalchemy as sa
from sqlalchemy import text

from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import get_settings
from wnba_oracle.db.engine import get_engine
from wnba_oracle.ingest.odds import fetch_odds_for_slate
from wnba_oracle.ingest.realsports import (
    PlatformAuthRequired,
    capture_live_headers,
    fetch_pool_for_date,
    headers_or_capture,
)
from wnba_oracle.ingest.rotowire import fetch_lineups

log = get_logger("oracle.job1")


@dataclass(frozen=True)
class Job1Result:
    slate_date: str
    n_pool: int
    n_odds: int
    n_lineups: int
    persisted_rows: int


JOB1_UPSERT = text(
    """
    INSERT INTO job1_enrichment (
        slate_date, player_id, real_sports_player_id, name, team, opponent,
        position, card_boost, features_json, captured_at
    ) VALUES (
        :slate_date, :player_id, :real_sports_player_id, :name, :team, :opponent,
        :position, :card_boost, :features_json, now()
    )
    ON CONFLICT (slate_date, player_id) DO UPDATE SET
        real_sports_player_id = EXCLUDED.real_sports_player_id,
        name = EXCLUDED.name,
        team = EXCLUDED.team,
        opponent = EXCLUDED.opponent,
        position = EXCLUDED.position,
        card_boost = EXCLUDED.card_boost,
        features_json = EXCLUDED.features_json,
        captured_at = now();
    """
)


def _device_uuid() -> str:
    return os.environ.get("WNBA_DEVICE_UUID", "wnba-oracle-prod-01-device")


def _device_name() -> str:
    return os.environ.get("WNBA_DEVICE_NAME", "wnba-oracle-prod-01")


async def _do_pool_fetch(slate_date: str) -> list:
    headers = await headers_or_capture(_device_uuid(), _device_name())

    async def _refresh():
        return await capture_live_headers(_device_uuid(), _device_name())

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            pool = await fetch_pool_for_date(
                slate_date, headers, client, refresh_headers=_refresh
            )
        except PlatformAuthRequired:
            # One more chance: force-refresh and retry once.
            headers = await capture_live_headers(_device_uuid(), _device_name())
            pool = await fetch_pool_for_date(
                slate_date, headers, client, refresh_headers=_refresh
            )
    return pool


def run(slate_date: str | None = None, *, dry_run: bool = False) -> Job1Result:
    settings = get_settings()
    sd = slate_date or dt.date.today().isoformat()
    log.info("job1_start", slate_date=sd, dry_run=dry_run)

    pool = asyncio.run(_do_pool_fetch(sd))
    log.info("job1_pool", n=len(pool))

    try:
        odds = fetch_odds_for_slate()
    except Exception as exc:
        log.warning("job1_odds_failed", reason=str(exc))
        odds = []

    try:
        lineups = fetch_lineups()
    except Exception as exc:
        log.warning("job1_lineups_failed", reason=str(exc))
        lineups = []

    # Build opponent / team map from odds + per-game roster join. For now
    # the platform pool gives team but not opponent; use the odds map.
    team_to_opp: dict[str, str] = {}
    for g in odds:
        team_to_opp[_short(g.home_team)] = _short(g.away_team)
        team_to_opp[_short(g.away_team)] = _short(g.home_team)

    rows = []
    for p in pool:
        features = {
            "primary_ranking": p.primary_ranking,
            "injury_status": p.injury_status,
        }
        rows.append(
            {
                "slate_date": sd,
                "player_id": int(p.platform_id) if p.platform_id.isdigit() else 0,
                "real_sports_player_id": p.platform_id,
                "name": p.display_name,
                "team": p.team,
                "opponent": team_to_opp.get(p.team, ""),
                "position": p.position,
                "card_boost": float(p.multiplier_bonus),
                "features_json": json.dumps(features),
            }
        )

    persisted = 0
    if not dry_run and settings.database_url:
        try:
            eng = get_engine()
        except RuntimeError as exc:
            log.error("job1_no_db", reason=str(exc))
            return Job1Result(sd, len(pool), len(odds), len(lineups), 0)
        with eng.begin() as conn:
            for row in rows:
                conn.execute(JOB1_UPSERT, row)
                persisted += 1

    log.info(
        "job1_done",
        slate_date=sd,
        n_pool=len(pool),
        n_odds=len(odds),
        n_lineups=len(lineups),
        persisted=persisted,
    )
    return Job1Result(sd, len(pool), len(odds), len(lineups), persisted)


def _short(full_name: str) -> str:
    from wnba_oracle.features.build import _WNBA_TEAM_NAME_TO_KEY

    return _WNBA_TEAM_NAME_TO_KEY.get(full_name, full_name[:3].upper())


def main() -> int:
    configure_logging("INFO")
    settings = get_settings()
    sd = dt.date.today().isoformat()
    try:
        run(sd, dry_run=settings.job1_dry_run)
    except Exception as exc:
        log.exception("job1_failed", error=str(exc))
        return 1
    return 0


_ = sa  # acknowledge import
