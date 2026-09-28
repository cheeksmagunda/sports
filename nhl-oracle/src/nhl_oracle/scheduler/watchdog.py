"""Public-schedule T-40 watchdog for the NHL daily five (observation only).

The runner reads the public NHL schedule and the public team-summary feed.
It does not call Real Sports and it does not invent a five-player pick.
Lock time is the earliest regular-season puck drop on the US/Eastern slate
date. That is a publication proxy until a contest lock is captured.

``contest_entry`` stays false. A missing full roster pool inside the T-40
window is an alert, not a lineup.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from nhl_oracle.calendar.season import season_label_for_date
from nhl_oracle.contract.boost_gate import NHL_EXPECTED_TEAM_COUNT, evaluate_boost_eligibility
from nhl_oracle.scheduler.t40 import t40_window

EASTERN = ZoneInfo("America/New_York")
REGULAR_SEASON_GAME_TYPE = 2


@dataclass(frozen=True)
class PublicGame:
    """One regular-season game from the public NHL schedule."""

    game_id: int
    start_at: datetime
    away: str
    home: str
    game_state: str
    season: int


@dataclass(frozen=True)
class T40WatchReport:
    """One watchdog observation. ``pick_player_ids`` stays empty without a pool."""

    status: str
    reason: str
    day: date
    checked_at: datetime
    games: int
    slate_teams: int
    earliest_start: datetime | None
    t40_open: datetime | None
    zero_boost_active: bool
    teams_observed: int
    teams_expected: int
    freeze_ready: bool
    contest_entry: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "day": self.day.isoformat(),
            "checked_at": self.checked_at.isoformat(),
            "games": self.games,
            "slate_teams": self.slate_teams,
            "earliest_start": (
                None if self.earliest_start is None else self.earliest_start.isoformat()
            ),
            "t40_open": None if self.t40_open is None else self.t40_open.isoformat(),
            "zero_boost_active": self.zero_boost_active,
            "teams_observed": self.teams_observed,
            "teams_expected": self.teams_expected,
            "freeze_ready": self.freeze_ready,
            "pick_player_ids": None,
            "contest_entry": self.contest_entry,
            "observation_only": True,
        }


def season_id_for_date(day: date) -> str:
    """NHL stats season id, for example ``20262027``."""

    start = season_label_for_date(day)
    return f"{start}{start + 1}"


def _parse_start(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def games_on_eastern_date(payload: dict[str, Any], day: date) -> tuple[PublicGame, ...]:
    """Regular-season games whose puck drop falls on ``day`` in US/Eastern."""

    found: list[PublicGame] = []
    for week in payload.get("gameWeek") or []:
        if not isinstance(week, dict):
            continue
        for game in week.get("games") or []:
            if not isinstance(game, dict):
                continue
            if game.get("gameType") != REGULAR_SEASON_GAME_TYPE:
                continue
            start_at = _parse_start(game.get("startTimeUTC"))
            if start_at is None or start_at.astimezone(EASTERN).date() != day:
                continue
            game_id = game.get("id")
            if not isinstance(game_id, int):
                continue
            away = str((game.get("awayTeam") or {}).get("abbrev") or "").strip()
            home = str((game.get("homeTeam") or {}).get("abbrev") or "").strip()
            if not away or not home:
                continue
            season = game.get("season")
            found.append(
                PublicGame(
                    game_id=game_id,
                    start_at=start_at,
                    away=away,
                    home=home,
                    game_state=str(game.get("gameState") or ""),
                    season=int(season) if isinstance(season, int) else 0,
                )
            )
    return tuple(sorted(found, key=lambda game: (game.start_at, game.game_id)))


def team_games_played_from_summary(payload: dict[str, Any]) -> dict[str, int]:
    """Map public team id to regular-season GP. An empty feed stays empty."""

    covered: dict[str, int] = {}
    for row in payload.get("data") or []:
        if not isinstance(row, dict):
            continue
        team_id = row.get("teamId")
        if team_id is None:
            continue
        games_played = row.get("gamesPlayed")
        if not isinstance(games_played, int) or games_played < 0:
            continue
        covered[str(team_id)] = games_played
    return covered


def evaluate_t40_watch(
    *,
    day: date,
    schedule: dict[str, Any],
    team_summary: dict[str, Any],
    now: datetime,
    freeze_ready: bool = False,
) -> T40WatchReport:
    """Report whether Tuesday-or-any slate is inside T-40 without a full pool.

    ``freeze_ready`` is injected by a caller that already scored a full roster
    pool. This function does not build a pick. The public runner leaves it
    false.
    """

    if now.tzinfo is None:
        raise ValueError("now_must_be_timezone_aware")
    games = games_on_eastern_date(schedule, day)
    coverage = team_games_played_from_summary(team_summary)
    eligibility = evaluate_boost_eligibility(coverage)
    teams = {team for game in games for team in (game.away, game.home)}
    earliest = games[0].start_at if games else None
    window = None if earliest is None else t40_window(earliest)
    base = T40WatchReport(
        status="idle",
        reason="no_regular_season_games",
        day=day,
        checked_at=now,
        games=len(games),
        slate_teams=len(teams),
        earliest_start=earliest,
        t40_open=None if window is None else window.open_at,
        zero_boost_active=not eligibility.boost_allowed,
        teams_observed=eligibility.teams_observed,
        teams_expected=NHL_EXPECTED_TEAM_COUNT,
        freeze_ready=freeze_ready,
    )
    if not games or window is None:
        return base
    if now < window.open_at:
        return T40WatchReport(
            status="waiting",
            reason="before_t40_window",
            day=base.day,
            checked_at=base.checked_at,
            games=base.games,
            slate_teams=base.slate_teams,
            earliest_start=base.earliest_start,
            t40_open=base.t40_open,
            zero_boost_active=base.zero_boost_active,
            teams_observed=base.teams_observed,
            teams_expected=base.teams_expected,
            freeze_ready=freeze_ready,
        )
    if freeze_ready:
        return T40WatchReport(
            status="ready",
            reason="freeze_ready",
            day=base.day,
            checked_at=base.checked_at,
            games=base.games,
            slate_teams=base.slate_teams,
            earliest_start=base.earliest_start,
            t40_open=base.t40_open,
            zero_boost_active=base.zero_boost_active,
            teams_observed=base.teams_observed,
            teams_expected=base.teams_expected,
            freeze_ready=True,
        )
    if now >= window.lock_at:
        reason = "past_lock_without_full_roster_freeze"
    else:
        reason = "inside_t40_without_full_roster_pool"
    return T40WatchReport(
        status="alert",
        reason=reason,
        day=base.day,
        checked_at=base.checked_at,
        games=base.games,
        slate_teams=base.slate_teams,
        earliest_start=base.earliest_start,
        t40_open=base.t40_open,
        zero_boost_active=base.zero_boost_active,
        teams_observed=base.teams_observed,
        teams_expected=base.teams_expected,
        freeze_ready=False,
    )


def render_markdown(report: T40WatchReport) -> str:
    """Job-summary markdown. No lineup is printed."""

    earliest = "none" if report.earliest_start is None else report.earliest_start.isoformat()
    opened = "none" if report.t40_open is None else report.t40_open.isoformat()
    lines = [
        f"# NHL T-40 watchdog ({report.checked_at.isoformat()})",
        "",
        f"- status: `{report.status}`",
        f"- reason: `{report.reason}`",
        f"- day: `{report.day.isoformat()}`",
        f"- games: {report.games}",
        f"- slate_teams: {report.slate_teams}",
        f"- earliest_puck_drop: `{earliest}`",
        f"- t40_open: `{opened}`",
        f"- zero_boost_active: {str(report.zero_boost_active).lower()}",
        f"- teams_observed: {report.teams_observed} of {report.teams_expected}",
        "- pick_player_ids: none",
        "- contest_entry: false",
        "",
        "Lock proxy is the earliest regular-season puck drop on the US/Eastern",
        "slate date. It is not a Real Sports contest lock. The no-boost picker",
        "runs only when a full roster pool is supplied. This runner does not",
        "invent one.",
        "",
    ]
    return "\n".join(lines)
