"""Minimal NFL season/week helpers (domain-owned; not a provider adapter)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SeasonWeek:
    season: int
    week: int | None
    note: str = ""


def season_week_for_date(day: date) -> SeasonWeek:
    """Approximate NFL season label from calendar date.

    NFL seasons are labeled by the calendar year of Week 1 (Sept). Dates in
    January–February belong to the prior season label. Week number is left
    None until a schedule source is wired — do not invent week from DOY alone.
    """

    if day.month < 3:
        season = day.year - 1
    elif day.month >= 9:
        season = day.year
    else:
        # Offseason / preseason ambiguity — still tag by upcoming season year
        season = day.year
    return SeasonWeek(season=season, week=None, note="week_unresolved_without_schedule")
