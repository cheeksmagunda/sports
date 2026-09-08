"""Public nflverse / nfldata schedule helpers (no Real Sports auth).

Downloads are optional; parsers work on already-fetched CSV text so CI stays
offline. Rights/attribution: nflverse / nfldata CC BY 4.0; underlying NFL data
remain owned by their respective owners (see DATA_ATTRIBUTION.md).
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

# Primary public source (Lee Sharpe / nflverse nfldata). Release-tag CSV may 404;
# raw games.csv is the stable offline-cacheable feed.
NFLVERSE_SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
NFLVERSE_SCHEDULE_URL_ALIASES: tuple[str, ...] = (
    NFLVERSE_SCHEDULE_URL,
    "https://github.com/nflverse/nfldata/raw/master/data/games.csv",
    "https://github.com/nflverse/nflverse-data/releases/download/schedules/schedules.csv",
)

# Preferred offline paths under a project data root (first hit wins).
SCHEDULE_RELATIVE_CANDIDATES = (
    Path("schedule") / "schedules.csv",
    Path("schedule") / "dense_schedules.csv",
    Path("cache") / "schedules.csv",
    Path("cache") / "nflverse_games.csv",
    Path("catalog") / "schedules.csv",
)

REGULAR_GAME_TYPES = frozenset({"REG", ""})
POSTSEASON_GAME_TYPES = frozenset({"WC", "DIV", "CON", "SB", "POST"})


@dataclass(frozen=True)
class ScheduledGame:
    season: int
    week: int
    game_id: str
    gameday: date | None
    home_team: str
    away_team: str
    game_type: str = "REG"


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


@dataclass(frozen=True)
class SeasonSlateCensus:
    """Continuous slate discovery for one season (observation only)."""

    season: int
    game_count: int
    regular_season_game_count: int
    postseason_game_count: int
    weeks: list[int]
    regular_weeks: list[int]
    missing_regular_weeks: list[int]
    games_per_week: dict[str, int]
    continuous_regular_slate: bool
    min_week: int | None
    max_week: int | None
    team_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_schedules_csv(text: str, *, season: int | None = None) -> list[ScheduledGame]:
    """Parse nflverse/nfldata schedules CSV text into ScheduledGame rows."""

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
        game_type = str(row.get("game_type") or "REG").strip().upper() or "REG"
        if game_type.startswith("PRE"):
            continue
        out.append(
            ScheduledGame(
                season=row_season,
                week=week,
                game_id=str(row.get("game_id") or ""),
                gameday=gameday,
                home_team=str(row.get("home_team") or ""),
                away_team=str(row.get("away_team") or ""),
                game_type=game_type,
            )
        )
    return out


def load_schedules_csv(path: Path, *, season: int | None = None) -> list[ScheduledGame]:
    """Load schedules from a local CSV path (offline fixtures / cached nflverse)."""

    if not path.is_file():
        raise FileNotFoundError(f"schedule csv missing: {path}")
    return parse_schedules_csv(path.read_text(encoding="utf-8"), season=season)


def try_load_schedules_csv(
    path: Path | None,
    *,
    season: int | None = None,
) -> list[ScheduledGame]:
    """Load schedules when path exists; empty list when missing/unreadable."""

    if path is None or not path.is_file():
        return []
    try:
        return load_schedules_csv(path, season=season)
    except (OSError, UnicodeError, csv.Error):
        return []


def resolve_schedule_csv_path(data_root: Path | None = None) -> Path | None:
    """Return first existing offline schedule CSV under a data root, else None."""

    if data_root is None:
        return None
    for rel in SCHEDULE_RELATIVE_CANDIDATES:
        candidate = data_root / rel
        if candidate.is_file():
            return candidate
    return None


def weeks_for_season(games: Iterable[ScheduledGame]) -> list[int]:
    return sorted({g.week for g in games if g.week > 0})


def games_for_season(
    games: Iterable[ScheduledGame],
    season: int,
    *,
    game_types: Sequence[str] | None = None,
) -> list[ScheduledGame]:
    """Return schedule rows for one season (optional game_type filter)."""

    allowed = {t.upper() for t in game_types} if game_types is not None else None
    out = [
        g
        for g in games
        if g.season == season and (allowed is None or g.game_type.upper() in allowed)
    ]
    return sorted(out, key=lambda g: (g.week, g.gameday or date.min, g.game_id))


def build_gameday_week_index(games: Iterable[ScheduledGame]) -> dict[date, int]:
    """Map gameday → week (first positive week wins for multi-game days)."""

    index: dict[date, int] = {}
    for game in games:
        if game.gameday is None or game.week <= 0:
            continue
        index.setdefault(game.gameday, game.week)
    return index


def week_for_gameday(
    games: Iterable[ScheduledGame],
    day: date,
    *,
    index: dict[date, int] | None = None,
) -> int | None:
    """Return the schedule week for an exact gameday match, else None."""

    if index is not None:
        return index.get(day)
    for game in games:
        if game.gameday == day and game.week > 0:
            return game.week
    return None


def games_in_week(games: Iterable[ScheduledGame], *, season: int, week: int) -> list[ScheduledGame]:
    return [g for g in games if g.season == season and g.week == week]


def summarize_season_slate(games: Iterable[ScheduledGame], season: int) -> SeasonSlateCensus:
    """Census one season's continuous slate (REG weeks 1..N without holes)."""

    season_games = games_for_season(games, season)
    reg = [g for g in season_games if g.game_type.upper() in REGULAR_GAME_TYPES]
    post = [g for g in season_games if g.game_type.upper() in POSTSEASON_GAME_TYPES]
    weeks = weeks_for_season(season_games)
    reg_weeks = weeks_for_season(reg)
    missing: list[int] = []
    continuous = False
    if reg_weeks:
        expected = list(range(reg_weeks[0], reg_weeks[-1] + 1))
        missing = [w for w in expected if w not in set(reg_weeks)]
        continuous = not missing and reg_weeks[0] == 1
    per_week: dict[str, int] = defaultdict(int)
    for g in season_games:
        per_week[str(g.week)] += 1
    teams: set[str] = set()
    for g in season_games:
        if g.home_team:
            teams.add(g.home_team)
        if g.away_team:
            teams.add(g.away_team)
    return SeasonSlateCensus(
        season=season,
        game_count=len(season_games),
        regular_season_game_count=len(reg),
        postseason_game_count=len(post),
        weeks=weeks,
        regular_weeks=reg_weeks,
        missing_regular_weeks=missing,
        games_per_week=dict(sorted(per_week.items(), key=lambda kv: int(kv[0]))),
        continuous_regular_slate=continuous,
        min_week=weeks[0] if weeks else None,
        max_week=weeks[-1] if weeks else None,
        team_count=len(teams),
    )


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


def season_week_census(
    games: Iterable[ScheduledGame],
    *,
    expected_weeks: int = 18,
) -> dict[str, Any]:
    """Per-season week continuity census (observation only).

    ``expected_weeks`` defaults to the modern 18-week regular season. Legacy
    17-week seasons still count as continuous via ``summarize_season_slate`` but
    only match ``full_regular_season_weeks`` when their REG weeks equal
    ``list(range(1, expected_weeks + 1))``.
    """

    rows = list(games)
    seasons = sorted({g.season for g in rows})
    expected = list(range(1, expected_weeks + 1))
    out_seasons: list[dict[str, Any]] = []
    full = 0
    continuous = 0
    for season in seasons:
        census = summarize_season_slate(rows, season)
        is_full = census.regular_weeks == expected
        if is_full:
            full += 1
        if census.continuous_regular_slate:
            continuous += 1
        out_seasons.append(
            {
                "season": season,
                "regular_week_count": len(census.regular_weeks),
                "regular_weeks": census.regular_weeks,
                "missing_regular_weeks": census.missing_regular_weeks,
                "regular_season_game_count": census.regular_season_game_count,
                "postseason_game_count": census.postseason_game_count,
                "game_count": census.game_count,
                "continuous_regular_slate": census.continuous_regular_slate,
                "full_regular_season_weeks": is_full,
            }
        )
    return {
        "contest_entry": False,
        "observation_only": True,
        "expected_weeks": expected_weeks,
        "full_season_week_count": full,
        "continuous_regular_season_count": continuous,
        "season_count": len(seasons),
        "seasons": out_seasons,
    }


def coverage_schedule_census(
    *,
    catalog_seasons: dict[str, list[int]] | dict[int, tuple[int, ...]] | dict[str, Any],
    games: Iterable[ScheduledGame],
    expected_weeks: int = 18,
) -> dict[str, Any]:
    """Join catalog seed anchors to continuous schedule slate census."""

    rows = list(games)
    dens = summarize_schedule_density(rows)
    week = season_week_census(rows, expected_weeks=expected_weeks)
    catalog_seed_count = 0
    per_season: list[dict[str, Any]] = []
    catalog_norm: dict[str, list[Any]] = {
        str(k): list(v) if v is not None else [] for k, v in catalog_seasons.items()
    }
    catalog_keys = sorted({int(k) for k in catalog_norm if str(k).isdigit()})
    schedule_by_season = {
        s: summarize_season_slate(rows, s) for s in sorted({g.season for g in rows})
    }
    for season in sorted(set(catalog_keys) | set(schedule_by_season.keys())):
        seed_ids = list(catalog_norm.get(str(season), []))
        catalog_seed_count += len(seed_ids)
        slate = schedule_by_season.get(season)
        if slate is None:
            per_season.append(
                {
                    "season": season,
                    "catalog_seed_count": len(seed_ids),
                    "schedule_game_count": 0,
                    "regular_season_game_count": 0,
                    "continuous_regular_slate": False,
                    "full_regular_season_weeks": False,
                    "schedule_games_beyond_seeds": 0,
                    "schedule_present": False,
                }
            )
            continue
        is_full = slate.regular_weeks == list(range(1, expected_weeks + 1))
        per_season.append(
            {
                "season": season,
                "catalog_seed_count": len(seed_ids),
                "schedule_game_count": slate.game_count,
                "regular_season_game_count": slate.regular_season_game_count,
                "postseason_game_count": slate.postseason_game_count,
                "regular_week_count": len(slate.regular_weeks),
                "missing_regular_weeks": slate.missing_regular_weeks,
                "continuous_regular_slate": slate.continuous_regular_slate,
                "full_regular_season_weeks": is_full,
                "schedule_games_beyond_seeds": max(slate.game_count - len(seed_ids), 0),
                "schedule_present": True,
            }
        )
    return {
        "contest_entry": False,
        "observation_only": True,
        "catalog_seed_count": catalog_seed_count,
        "catalog_season_count": len(catalog_keys),
        "game_count": dens.game_count,
        "season_count": dens.season_count,
        "schedule_density": dens.to_dict(),
        "week_census": week,
        "continuous_regular_season_count": week["continuous_regular_season_count"],
        "per_season": per_season,
        "seasons": {str(row["season"]): row for row in per_season},
    }


# Backward-compatible alias used by earlier gap-1 drafts.
def schedule_coverage_census(
    *,
    catalog_seasons: dict[str, list[int]] | dict[int, tuple[int, ...]] | dict[str, Any],
    games: Iterable[ScheduledGame],
) -> dict[str, Any]:
    return coverage_schedule_census(catalog_seasons=catalog_seasons, games=games)


def research_schedule_summary(
    *,
    project_root: Path | None = None,
    schedule_path: Path | None = None,
    catalog_seed_count: int | None = None,
    catalog_seasons: dict[str, list[int]] | dict[int, tuple[int, ...]] | None = None,
) -> dict[str, Any]:
    """Offline schedule density JSON for research routes (never enables entry)."""

    from nfl_oracle.data.paths import resolve_data_paths

    paths = resolve_data_paths(project_root) if project_root is not None else resolve_data_paths()
    resolved = schedule_path or resolve_schedule_csv_path(paths.root)
    games = try_load_schedules_csv(resolved)
    dens = summarize_schedule_density(games)
    week_census = season_week_census(games, expected_weeks=18)
    continuous = int(week_census["continuous_regular_season_count"])
    slate_samples: dict[str, Any] = {}
    for season in dens.seasons:
        if season >= 2018:
            slate_samples[str(season)] = summarize_season_slate(games, season).to_dict()
    payload: dict[str, Any] = {
        "contest_entry": False,
        "observation_only": True,
        "attribution": {
            "license": "CC BY 4.0",
            "source": "nflverse/nfldata games.csv",
            "url": NFLVERSE_SCHEDULE_URL,
        },
        "path_exists": resolved.is_file() if resolved is not None else False,
        "path": str(resolved) if resolved is not None else None,
        "density": dens.to_dict(),
        "gameday_index_size": len(build_gameday_week_index(games)),
        "continuous_regular_season_count": continuous,
        "continuous_regular_season_ratio": (
            continuous / dens.season_count if dens.season_count else 0.0
        ),
        "week_census": week_census,
        "slate_samples": slate_samples,
    }
    if catalog_seed_count is not None:
        payload["vs_catalog"] = catalog_vs_schedule_density(
            catalog_seed_count=catalog_seed_count,
            schedule_game_count=dens.game_count,
        )
    if catalog_seasons is not None:
        payload["coverage_census"] = coverage_schedule_census(
            catalog_seasons=catalog_seasons,
            games=games,
        )
    return payload
