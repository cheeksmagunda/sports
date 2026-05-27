"""Basketball-Reference WNBA scraper.

Designated fallback for stats.wnba.com outages. Slower (rate-limited to
1 req per 3s by bref ToS), less granular per-game advanced stats, but
HTML schema has been stable since the 1997 inaugural season.

Endpoints we currently rely on:
- /wnba/players/{letter}/  to enumerate active players (rarely needed
  because nba_api static catalog covers this).
- /wnba/teams/{TEAM}/{year}.html  for team season stats (pace, ORTG, DRTG).
- /wnba/players/{letter}/{slug}.html  for season averages.

Use only when the corresponding stats.wnba.com endpoint has returned
a 5xx for more than 10 minutes. The orchestrator (Step 8) flips a Redis
flag `wnba.bref_fallback=1` to enable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx
import polars as pl
from bs4 import BeautifulSoup

from wnba_oracle.common.logging import get_logger
from wnba_oracle.ingest.cache import cache_get, cache_put

log = get_logger("oracle.ingest.bref_fallback")

BASE = "https://www.basketball-reference.com"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}
RATE_LIMIT_SECONDS = 3.5


@dataclass(frozen=True)
class TeamSeasonRow:
    team_abbr: str
    year: int
    games: int
    pace: float | None
    off_rtg: float | None
    def_rtg: float | None
    ts_pct: float | None
    efg_pct: float | None


def fetch_team_season(team_abbr: str, year: int, *, use_cache: bool = True) -> TeamSeasonRow:
    """Pull team season meta. Cached aggressively (24h) because it rarely
    moves within a slate.
    """
    url = f"{BASE}/wnba/teams/{team_abbr}/{year}.html"
    cache_key = f"bref::team::{team_abbr}::{year}"
    params = None
    if use_cache:
        cached = cache_get(cache_key, params, ttl_s=24 * 3600.0)
        if cached is not None:
            return TeamSeasonRow(**cached["row"])

    log.info("bref_fetch_team_season", team=team_abbr, year=year)
    time.sleep(RATE_LIMIT_SECONDS)
    with httpx.Client(timeout=20.0, headers=DEFAULT_HEADERS) as client:
        r = client.get(url)
        r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    # The advanced table is usually in a comment block in bref's HTML.
    row = TeamSeasonRow(
        team_abbr=team_abbr,
        year=year,
        games=_int_or_none(soup, '[data-stat="games"]') or 0,
        pace=_float_or_none(soup, '[data-stat="pace"]'),
        off_rtg=_float_or_none(soup, '[data-stat="off_rtg"]'),
        def_rtg=_float_or_none(soup, '[data-stat="def_rtg"]'),
        ts_pct=_float_or_none(soup, '[data-stat="ts_pct"]'),
        efg_pct=_float_or_none(soup, '[data-stat="efg_pct"]'),
    )
    if use_cache:
        cache_put(cache_key, params, {"row": row.__dict__})
    return row


def _int_or_none(soup: BeautifulSoup, selector: str) -> int | None:
    el = soup.select_one(selector)
    if el is None:
        return None
    try:
        return int(el.get_text(strip=True).replace(",", ""))
    except ValueError:
        return None


def _float_or_none(soup: BeautifulSoup, selector: str) -> float | None:
    el = soup.select_one(selector)
    if el is None:
        return None
    try:
        return float(el.get_text(strip=True))
    except ValueError:
        return None


def teams_to_polars(rows: list[TeamSeasonRow]) -> pl.DataFrame:
    return pl.from_dicts([r.__dict__ for r in rows]) if rows else pl.DataFrame()
