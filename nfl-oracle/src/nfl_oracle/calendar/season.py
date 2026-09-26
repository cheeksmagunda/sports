"""Minimal NFL season/week helpers (domain-owned; not a provider adapter)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from nfl_oracle.calendar.schedule import ScheduledGame, week_for_gameday

EASTERN = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class SeasonWeek:
    season: int
    week: int | None
    note: str = ""


def eastern_today(now: datetime | None = None) -> date:
    """Calendar date in US/Eastern for the given instant (default: now)."""

    current = now or datetime.now(UTC)
    return current.astimezone(EASTERN).date()


def default_schedule_season_max(now: datetime | None = None) -> int:
    """Upper bound for offline schedule cache downloads."""

    return season_label_for_date(eastern_today(now))


def latest_two_seasons(rows: Iterable[Mapping[str, object]]) -> tuple[int, int]:
    """Latest two distinct season labels present in a tabular dataset."""

    seasons = sorted(
        {
            int(value)
            for row in rows
            if (value := row.get("season")) is not None and str(value).isdigit()
        }
    )
    if len(seasons) < 2:
        raise ValueError("fewer_than_two_seasons_in_dataset")
    return seasons[-2], seasons[-1]


def season_label_for_date(day: date) -> int:
    """Approximate NFL season label from calendar date.

    NFL seasons are labeled by the calendar year of Week 1 (Sept). Dates in
    January–February belong to the prior season label.
    """

    if day.month < 3:
        return day.year - 1
    if day.month >= 9:
        return day.year
    # Offseason / preseason ambiguity — still tag by upcoming season year
    return day.year


def season_week_for_date(
    day: date,
    *,
    schedule: Iterable[ScheduledGame] | None = None,
) -> SeasonWeek:
    """Resolve season label; week only when an offline schedule match exists.

    Do not invent week from day-of-year alone — that leaks false precision.
    """

    season = season_label_for_date(day)
    if schedule is not None:
        week = week_for_gameday(schedule, day)
        if week is not None:
            return SeasonWeek(season=season, week=week, note="week_from_schedule")
    return SeasonWeek(season=season, week=None, note="week_unresolved_without_schedule")
