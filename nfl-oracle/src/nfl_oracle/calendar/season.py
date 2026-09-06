"""Minimal NFL season/week helpers (domain-owned; not a provider adapter)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from nfl_oracle.calendar.schedule import ScheduledGame, week_for_gameday


@dataclass(frozen=True)
class SeasonWeek:
    season: int
    week: int | None
    note: str = ""


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
