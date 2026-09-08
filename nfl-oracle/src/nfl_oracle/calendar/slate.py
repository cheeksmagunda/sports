"""Week / slate resolution over dense offline schedules (observation only).

Given a calendar date or (season, week), return the week's games and
team→opponent map. Never invents weeks without schedule rows; never enables
contest entry.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from nfl_oracle.calendar.schedule import (
    ScheduledGame,
    build_gameday_week_index,
    games_in_week,
    resolve_schedule_csv_path,
    try_load_schedules_csv,
    week_for_gameday,
)
from nfl_oracle.calendar.season import season_label_for_date

ResolveMode = Literal[
    "season_week",
    "date_exact_gameday",
    "date_week_span",
    "unresolved",
]


@dataclass(frozen=True)
class SlateResolution:
    """Resolved NFL week slate (games + opponents) from offline schedules."""

    season: int | None
    week: int | None
    games: tuple[ScheduledGame, ...]
    opponents: dict[str, str]
    resolve_mode: ResolveMode
    note: str = ""
    query_date: date | None = None

    @property
    def resolved(self) -> bool:
        return (
            self.season is not None
            and self.week is not None
            and len(self.games) > 0
            and self.resolve_mode != "unresolved"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contest_entry": False,
            "observation_only": True,
            "resolved": self.resolved,
            "season": self.season,
            "week": self.week,
            "game_count": len(self.games),
            "games": [scheduled_game_to_dict(g) for g in self.games],
            "opponents": dict(sorted(self.opponents.items())),
            "teams": sorted(self.opponents),
            "resolve_mode": self.resolve_mode,
            "note": self.note,
            "query_date": self.query_date.isoformat() if self.query_date else None,
        }


def scheduled_game_to_dict(game: ScheduledGame) -> dict[str, Any]:
    """JSON-friendly ScheduledGame row."""

    return {
        "season": game.season,
        "week": game.week,
        "game_id": game.game_id,
        "gameday": game.gameday.isoformat() if game.gameday else None,
        "home_team": game.home_team,
        "away_team": game.away_team,
        "game_type": game.game_type,
        "opponent_home": game.away_team,
        "opponent_away": game.home_team,
    }


def opponents_by_team(games: Iterable[ScheduledGame]) -> dict[str, str]:
    """Map each team abbreviation to its opponent on this slate.

    Last matchup wins if a team somehow appears twice (should not happen in REG).
    """

    out: dict[str, str] = {}
    for game in games:
        if game.home_team and game.away_team:
            out[game.home_team] = game.away_team
            out[game.away_team] = game.home_team
    return out


def opponent_for_team(
    games: Iterable[ScheduledGame],
    team: str,
) -> str | None:
    """Return the opponent for ``team`` on the given games, else None."""

    key = team.strip().upper()
    mapping = opponents_by_team(games)
    # Prefer exact, then case-insensitive.
    if key in mapping:
        return mapping[key]
    for abbr, opp in mapping.items():
        if abbr.upper() == key:
            return opp
    return None


def _sorted_week_games(
    games: Iterable[ScheduledGame],
    *,
    season: int,
    week: int,
) -> tuple[ScheduledGame, ...]:
    rows = games_in_week(games, season=season, week=week)
    rows = sorted(rows, key=lambda g: (g.gameday or date.min, g.game_id))
    return tuple(rows)


def resolve_slate_for_season_week(
    games: Iterable[ScheduledGame],
    *,
    season: int,
    week: int,
) -> SlateResolution:
    """Return games + opponents for an explicit season+week."""

    rows = list(games)
    week_games = _sorted_week_games(rows, season=season, week=week)
    if not week_games:
        return SlateResolution(
            season=season,
            week=week,
            games=(),
            opponents={},
            resolve_mode="unresolved",
            note="no_games_for_season_week",
        )
    return SlateResolution(
        season=season,
        week=week,
        games=week_games,
        opponents=opponents_by_team(week_games),
        resolve_mode="season_week",
        note="resolved_from_season_week",
    )


def _week_spans_for_season(
    games: Sequence[ScheduledGame],
    season: int,
) -> dict[int, tuple[date, date]]:
    """week → (min_gameday, max_gameday) for games with known gamedays."""

    spans: dict[int, list[date]] = {}
    for game in games:
        if game.season != season or game.week <= 0 or game.gameday is None:
            continue
        spans.setdefault(game.week, []).append(game.gameday)
    return {week: (min(days), max(days)) for week, days in spans.items() if days}


def resolve_slate_for_date(
    games: Iterable[ScheduledGame],
    day: date,
    *,
    index: dict[date, int] | None = None,
) -> SlateResolution:
    """Resolve week slate from a calendar date via dense schedule census.

    Resolution order:
    1. Exact gameday match → that week's slate
    2. Date falls inside a week's [min_gameday, max_gameday] span
    3. Unresolved (do not invent a week)
    """

    rows = list(games)
    season = season_label_for_date(day)
    gameday_index = index if index is not None else build_gameday_week_index(rows)
    exact_week = week_for_gameday(rows, day, index=gameday_index)
    if exact_week is not None:
        # Prefer season from the matched game when available.
        matched = [g for g in rows if g.gameday == day and g.week == exact_week]
        if matched:
            season = matched[0].season
        slate = resolve_slate_for_season_week(rows, season=season, week=exact_week)
        return SlateResolution(
            season=slate.season,
            week=slate.week,
            games=slate.games,
            opponents=slate.opponents,
            resolve_mode="date_exact_gameday",
            note="week_from_exact_gameday",
            query_date=day,
        )

    spans = _week_spans_for_season(rows, season)
    for week in sorted(spans):
        lo, hi = spans[week]
        if lo <= day <= hi:
            slate = resolve_slate_for_season_week(rows, season=season, week=week)
            return SlateResolution(
                season=slate.season,
                week=slate.week,
                games=slate.games,
                opponents=slate.opponents,
                resolve_mode="date_week_span",
                note="week_from_gameday_span",
                query_date=day,
            )

    return SlateResolution(
        season=season,
        week=None,
        games=(),
        opponents={},
        resolve_mode="unresolved",
        note="week_unresolved_for_date",
        query_date=day,
    )


def resolve_slate(
    games: Iterable[ScheduledGame],
    *,
    season: int | None = None,
    week: int | None = None,
    day: date | None = None,
    index: dict[date, int] | None = None,
) -> SlateResolution:
    """Unified slate resolver: prefer explicit season+week, else date."""

    if season is not None and week is not None:
        return resolve_slate_for_season_week(games, season=season, week=week)
    if day is not None:
        return resolve_slate_for_date(games, day, index=index)
    return SlateResolution(
        season=season,
        week=week,
        games=(),
        opponents={},
        resolve_mode="unresolved",
        note="season_week_or_date_required",
    )


def research_schedule_slate(
    *,
    project_root: Path | None = None,
    schedule_path: Path | None = None,
    season: int | None = None,
    week: int | None = None,
    day: date | None = None,
    team: str | None = None,
) -> dict[str, Any]:
    """Offline schedule slate JSON for research routes (never enables entry)."""

    from nfl_oracle.data.paths import resolve_data_paths

    paths = resolve_data_paths(project_root) if project_root is not None else resolve_data_paths()
    resolved = schedule_path or resolve_schedule_csv_path(paths.root)
    games = try_load_schedules_csv(resolved)
    slate = resolve_slate(games, season=season, week=week, day=day)
    payload = slate.to_dict()
    payload["path_exists"] = resolved.is_file() if resolved is not None else False
    payload["path"] = str(resolved) if resolved is not None else None
    payload["schedule_game_count"] = len(games)
    if team:
        opp = opponent_for_team(slate.games, team) if slate.games else None
        payload["team_query"] = team.strip().upper()
        payload["team_opponent"] = opp
        payload["team_on_slate"] = opp is not None
    return payload
