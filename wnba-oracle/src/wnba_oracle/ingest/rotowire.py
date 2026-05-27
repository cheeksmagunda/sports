"""RotoWire WNBA lineup scraper.

Pulls expected and confirmed lineups for today's WNBA slate.
- Expected lineups: ~24 hours before tipoff.
- Confirmed lineups: same-day, populated about 30-90 minutes before tip.

The page is a static HTML render so we parse it with BeautifulSoup. We do
NOT use Playwright here; RotoWire's WNBA page does not require JS to expose
the data.

Sample URL: https://www.rotowire.com/basketball/wnba-lineups.php
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import polars as pl
from bs4 import BeautifulSoup

from wnba_oracle.common.logging import get_logger
from wnba_oracle.ingest.cache import cache_get, cache_put

log = get_logger("oracle.ingest.rotowire")

URL = "https://www.rotowire.com/basketball/wnba-lineups.php"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}


@dataclass(frozen=True)
class LineupEntry:
    team: str
    opponent: str
    is_home: bool
    starter_slot: int  # 1..5 by position order in the page
    player_name: str
    position: str
    injury_status: str  # "" if active
    confirmed: bool  # True if "Confirmed" badge present, else expected


def fetch_lineups(
    *,
    use_cache: bool = True,
    cache_ttl_s: float = 600.0,
) -> list[LineupEntry]:
    """Scrape RotoWire's WNBA lineups page. Cached for 10 min by default.

    Schema: returns one LineupEntry per (game, team, starter_slot 1..5).
    Players RotoWire flags as IL/DTD/OUT have `injury_status` set; pickers
    should drop or downweight accordingly.
    """
    if use_cache:
        cached = cache_get(URL, None, ttl_s=cache_ttl_s)
        if cached is not None:
            return [LineupEntry(**row) for row in cached["entries"]]

    log.info("rotowire_fetch", url=URL)
    with httpx.Client(timeout=20.0, headers=DEFAULT_HEADERS) as client:
        r = client.get(URL)
        r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    entries: list[LineupEntry] = []
    for box in soup.select("div.lineup.is-wnba"):
        teams = box.select("div.lineup__abbr")
        if len(teams) < 2:
            continue
        away = teams[0].get_text(strip=True).upper()
        home = teams[1].get_text(strip=True).upper()
        confirmed_badge = box.select_one(".lineup__status")
        confirmed = "confirmed" in (confirmed_badge.get_text("").lower() if confirmed_badge else "")
        # Two lists: visiting + home starters.
        sides = [
            ("visit", away, home, False),
            ("home", home, away, True),
        ]
        for cls, team_abbr, opp_abbr, is_home in sides:
            list_el = box.select_one(f"ul.lineup__list.is-{cls}")
            if list_el is None:
                continue
            for i, li in enumerate(list_el.select("li.lineup__player"), start=1):
                # Each li has the position badge, player link, and injury badge.
                pos_el = li.select_one(".lineup__pos")
                pos = pos_el.get_text(strip=True) if pos_el else ""
                name_el = li.select_one("a")
                player_name = name_el.get_text(strip=True) if name_el else ""
                injury_el = li.select_one(".lineup__inj")
                injury = injury_el.get_text(strip=True) if injury_el else ""
                if not player_name:
                    continue
                entries.append(
                    LineupEntry(
                        team=team_abbr,
                        opponent=opp_abbr,
                        is_home=is_home,
                        starter_slot=i,
                        player_name=player_name,
                        position=pos,
                        injury_status=injury,
                        confirmed=confirmed,
                    )
                )
    if use_cache:
        cache_put(URL, None, {"entries": [e.__dict__ for e in entries]})
    return entries


def lineups_to_polars(entries: list[LineupEntry]) -> pl.DataFrame:
    return pl.from_dicts([e.__dict__ for e in entries]) if entries else pl.DataFrame()
