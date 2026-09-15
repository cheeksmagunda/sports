"""Week-close gate helpers: final slate identity, live finalization, buffer.

Session-free. Uses the public nflverse/nfldata games.csv (CC BY 4.0) for both
schedule identity and score presence. Exact whistle time is not in that feed,
so the 1h post-final buffer is applied as:

  now >= kickoff_eastern + MIN_GAME_DURATION + FINALIZATION_BUFFER

AND the final game must have scores (or a result) on a live download. Score
presence is the finalization signal; the kickoff-relative floor keeps the gate
from firing mid-game if a row is briefly malformed, and gives providers about
an hour after a typical full-length game before week-close may run. A long OT
game that finalizes after that floor still waits on scores.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")

# Earliest plausible regulation length before we will accept "final + buffer".
MIN_GAME_DURATION = timedelta(hours=3)
# Required settle time after that earliest-final floor (and after scores exist).
FINALIZATION_BUFFER = timedelta(hours=1)


@dataclass(frozen=True)
class WeekGame:
    season: int
    week: int
    game_id: str
    gameday: date
    gametime: str  # HH:MM Eastern, may be empty
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    result: str  # raw result cell; non-empty means nflverse recorded an outcome


@dataclass(frozen=True)
class WeekFinalSlate:
    season: int
    week: int
    final_gameday: date
    final_game: WeekGame


@dataclass(frozen=True)
class GateDecision:
    should_run: bool
    reason: str
    as_of: date
    is_final_slate_day: bool
    season: int | None
    week: int | None
    final_gameday: date | None
    final_game_id: str
    final_kickoff_eastern: datetime | None
    finalized: bool
    buffer_elapsed: bool

    def as_outputs(self) -> dict[str, str]:
        return {
            "should_run": str(self.should_run).lower(),
            "reason": self.reason,
            "as_of": self.as_of.isoformat(),
            "is_final_slate_day": str(self.is_final_slate_day).lower(),
            "season": str(self.season) if self.season is not None else "",
            "week": str(self.week) if self.week is not None else "",
            "final_gameday": self.final_gameday.isoformat() if self.final_gameday else "",
            "final_game_id": self.final_game_id,
            "finalized": str(self.finalized).lower(),
            "buffer_elapsed": str(self.buffer_elapsed).lower(),
        }


def _parse_optional_int(raw: str | None) -> int | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_week_games(raw_csv: str) -> list[WeekGame]:
    """Non-preseason games from an nflverse games/schedules CSV."""

    out: list[WeekGame] = []
    for row in csv.DictReader(io.StringIO(raw_csv)):
        game_type = str(row.get("game_type") or "REG").strip().upper()
        if game_type.startswith("PRE"):
            continue
        try:
            season = int(row.get("season") or 0)
            week = int(row.get("week") or 0)
        except ValueError:
            continue
        raw_day = (row.get("gameday") or "").strip()
        if season <= 0 or week <= 0 or not raw_day:
            continue
        try:
            gameday = date.fromisoformat(raw_day)
        except ValueError:
            continue
        out.append(
            WeekGame(
                season=season,
                week=week,
                game_id=str(row.get("game_id") or "").strip(),
                gameday=gameday,
                gametime=(row.get("gametime") or "").strip(),
                home_team=str(row.get("home_team") or "").strip(),
                away_team=str(row.get("away_team") or "").strip(),
                home_score=_parse_optional_int(row.get("home_score")),
                away_score=_parse_optional_int(row.get("away_score")),
                result=str(row.get("result") or "").strip(),
            )
        )
    return out


def week_containing(games: list[WeekGame], day: date) -> tuple[int, int] | None:
    for game in games:
        if game.gameday == day:
            return game.season, game.week
    return None


def kickoff_eastern(game: WeekGame) -> datetime | None:
    """Kickoff instant in US/Eastern, or None when gametime is missing/invalid."""

    if not game.gametime:
        return None
    try:
        hour_s, minute_s = game.gametime.split(":", 1)
        hour = int(hour_s)
        minute = int(minute_s)
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return datetime(
        game.gameday.year,
        game.gameday.month,
        game.gameday.day,
        hour,
        minute,
        tzinfo=EASTERN,
    )


def game_sort_key(game: WeekGame) -> tuple[datetime, str]:
    """Latest kickoff wins; missing gametime sorts after noon that gameday."""

    kick = kickoff_eastern(game)
    if kick is not None:
        return (kick, game.game_id)
    return (
        datetime(
            game.gameday.year,
            game.gameday.month,
            game.gameday.day,
            12,
            0,
            tzinfo=EASTERN,
        ),
        game.game_id,
    )


def is_game_finalized(game: WeekGame) -> bool:
    """True when nflverse has recorded an outcome (scores and/or result)."""

    if game.result:
        return True
    return game.home_score is not None and game.away_score is not None


def final_slate_for_week(games: list[WeekGame], *, season: int, week: int) -> WeekFinalSlate | None:
    week_games = [g for g in games if g.season == season and g.week == week]
    if not week_games:
        return None
    final_game = max(week_games, key=game_sort_key)
    return WeekFinalSlate(
        season=season,
        week=week,
        final_gameday=final_game.gameday,
        final_game=final_game,
    )


def resolve_week_final(games: list[WeekGame], *, as_of: date) -> WeekFinalSlate | None:
    """Final slate for the NFL week that contains `as_of`, if any.

    If `as_of` is not itself a gameday, look backward up to 6 days for the most
    recent gameday and use that week's final slate.
    """

    for offset in range(0, 7):
        candidate = as_of - timedelta(days=offset)
        identity = week_containing(games, candidate)
        if identity is None:
            continue
        season, week = identity
        return final_slate_for_week(games, season=season, week=week)
    return None


def is_final_slate_day(final: WeekFinalSlate | None, day: date) -> bool:
    return final is not None and final.final_gameday == day


def buffer_deadline(game: WeekGame) -> datetime | None:
    """Earliest instant week-close may fire for this final game."""

    kick = kickoff_eastern(game)
    if kick is None:
        return None
    return kick + MIN_GAME_DURATION + FINALIZATION_BUFFER


def buffer_elapsed(game: WeekGame, *, now: datetime) -> bool:
    deadline = buffer_deadline(game)
    if deadline is None:
        # Without gametime, do not invent a buffer; require the next Eastern
        # calendar day so we never fire during an unknown kickoff evening.
        eastern_now = now.astimezone(EASTERN)
        return eastern_now.date() > game.gameday
    return now.astimezone(EASTERN) >= deadline


def evaluate_gate(
    games: list[WeekGame],
    *,
    as_of: date,
    now: datetime | None = None,
) -> GateDecision:
    """Decide whether week-close should run for `as_of` at `now`."""

    current = now or datetime.now(UTC)
    final = resolve_week_final(games, as_of=as_of)
    final_day = is_final_slate_day(final, as_of)

    if final is None:
        return GateDecision(
            should_run=False,
            reason="no_week_context",
            as_of=as_of,
            is_final_slate_day=False,
            season=None,
            week=None,
            final_gameday=None,
            final_game_id="",
            final_kickoff_eastern=None,
            finalized=False,
            buffer_elapsed=False,
        )

    game = final.final_game
    kick = kickoff_eastern(game)
    finalized = is_game_finalized(game)
    elapsed = buffer_elapsed(game, now=current)

    if not final_day:
        reason = "not_final_slate_day"
        should_run = False
    elif not finalized:
        reason = "final_game_not_finalized"
        should_run = False
    elif not elapsed:
        reason = "buffer_not_elapsed"
        should_run = False
    else:
        reason = "ready"
        should_run = True

    return GateDecision(
        should_run=should_run,
        reason=reason,
        as_of=as_of,
        is_final_slate_day=final_day,
        season=final.season,
        week=final.week,
        final_gameday=final.final_gameday,
        final_game_id=game.game_id,
        final_kickoff_eastern=kick,
        finalized=finalized,
        buffer_elapsed=elapsed,
    )


def default_as_of(now: datetime | None = None) -> date:
    current = now or datetime.now(UTC)
    return current.astimezone(EASTERN).date()


def target_day_is_week_final(
    games: list[WeekGame],
    *,
    target_day: date,
) -> bool:
    """True when target_day is the final gameday of its NFL week (day-close supersede)."""

    identity = week_containing(games, target_day)
    if identity is None:
        return False
    season, week = identity
    final = final_slate_for_week(games, season=season, week=week)
    return is_final_slate_day(final, target_day)
