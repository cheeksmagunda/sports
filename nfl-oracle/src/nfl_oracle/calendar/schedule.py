"""Public nflverse schedule helpers (no Real Sports auth).

Downloads are optional; parsers work on already-fetched CSV text so CI stays
offline. Rights/attribution: nflverse CC BY 4.0; underlying NFL data remain
owned by their respective owners (see Drive strategy doc).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

NFLVERSE_SCHEDULE_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/schedules/schedules.csv"
)


@dataclass(frozen=True)
class ScheduledGame:
    season: int
    week: int
    game_id: str
    gameday: date | None
    home_team: str
    away_team: str


def parse_schedules_csv(text: str, *, season: int | None = None) -> list[ScheduledGame]:
    """Parse nflverse schedules.csv text into ScheduledGame rows."""

    reader = csv.DictReader(io.StringIO(text))
    out: list[ScheduledGame] = []
    for row in reader:
        try:
            row_season = int(row.get("season") or 0)
            week = int(row.get("week") or 0)
        except ValueError:
            continue
        if season is not None and row_season != season:
            continue
        gameday_raw = (row.get("gameday") or "").strip()
        gameday: date | None
        try:
            gameday = date.fromisoformat(gameday_raw) if gameday_raw else None
        except ValueError:
            gameday = None
        out.append(
            ScheduledGame(
                season=row_season,
                week=week,
                game_id=str(row.get("game_id") or ""),
                gameday=gameday,
                home_team=str(row.get("home_team") or ""),
                away_team=str(row.get("away_team") or ""),
            )
        )
    return out


def weeks_for_season(games: Iterable[ScheduledGame]) -> list[int]:
    return sorted({g.week for g in games if g.week > 0})
