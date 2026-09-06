"""Public nflverse schedule helpers (no Real Sports auth).

Downloads are optional; parsers work on already-fetched CSV text so CI stays
offline. Rights/attribution: nflverse CC BY 4.0; underlying NFL data remain
owned by their respective owners (see Drive strategy doc).
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

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


@dataclass(frozen=True)
class ScheduleDensity:
    """Offline schedule fixture density (observation only)."""

    season_count: int
    game_count: int
    week_count: int
    mean_games_per_season: float
    mean_games_per_week: float
    min_games_per_season: int | None
    max_games_per_season: int | None
    seasons: list[int]
    weeks_by_season: dict[str, list[int]]
    team_count: int
    missing_gameday_count: int
    unique_matchup_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
        if row_season <= 0 or week <= 0:
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


def load_schedules_csv(path: Path, *, season: int | None = None) -> list[ScheduledGame]:
    """Load schedules from a local CSV path (offline fixtures / cached nflverse)."""

    return parse_schedules_csv(path.read_text(encoding="utf-8"), season=season)


def weeks_for_season(games: Iterable[ScheduledGame]) -> list[int]:
    return sorted({g.week for g in games if g.week > 0})


def week_for_gameday(games: Iterable[ScheduledGame], day: date) -> int | None:
    """Return the schedule week for an exact gameday match, else None."""

    for game in games:
        if game.gameday == day and game.week > 0:
            return game.week
    return None


def games_in_week(games: Iterable[ScheduledGame], *, season: int, week: int) -> list[ScheduledGame]:
    return [g for g in games if g.season == season and g.week == week]


def summarize_schedule_density(games: Iterable[ScheduledGame]) -> ScheduleDensity:
    """Summarize offline schedule fixture density for STATUS / research honesty."""

    rows = list(games)
    by_season: dict[int, list[ScheduledGame]] = defaultdict(list)
    teams: set[str] = set()
    missing_gameday = 0
    matchups: set[tuple[int, str, str]] = set()
    for game in rows:
        by_season[game.season].append(game)
        if game.home_team:
            teams.add(game.home_team)
        if game.away_team:
            teams.add(game.away_team)
        if game.gameday is None:
            missing_gameday += 1
        if game.home_team and game.away_team:
            matchups.add((game.season, game.home_team, game.away_team))

    season_keys = sorted(by_season)
    season_counts = [len(by_season[s]) for s in season_keys]
    game_count = len(rows)
    season_count = len(season_keys)
    week_count = len({(g.season, g.week) for g in rows if g.week > 0})
    mean_per_season = (game_count / season_count) if season_count else 0.0
    mean_per_week = (game_count / week_count) if week_count else 0.0
    weeks_by_season = {str(season): weeks_for_season(by_season[season]) for season in season_keys}
    return ScheduleDensity(
        season_count=season_count,
        game_count=game_count,
        week_count=week_count,
        mean_games_per_season=mean_per_season,
        mean_games_per_week=mean_per_week,
        min_games_per_season=min(season_counts) if season_counts else None,
        max_games_per_season=max(season_counts) if season_counts else None,
        seasons=season_keys,
        weeks_by_season=weeks_by_season,
        team_count=len(teams),
        missing_gameday_count=missing_gameday,
        unique_matchup_count=len(matchups),
    )


def catalog_vs_schedule_density(
    *,
    catalog_seed_count: int,
    schedule_game_count: int,
) -> dict[str, Any]:
    """Compare seed-catalog density against schedule census (observation only)."""

    coverage_ratio = catalog_seed_count / schedule_game_count if schedule_game_count > 0 else 0.0
    return {
        "catalog_seed_count": catalog_seed_count,
        "schedule_game_count": schedule_game_count,
        "seed_to_schedule_ratio": coverage_ratio,
        "schedule_games_beyond_seeds": max(schedule_game_count - catalog_seed_count, 0),
        "contest_entry": False,
        "observation_only": True,
    }
