"""NBA season labeling helpers (domain-owned; not a provider adapter)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Public NBA calendar fact published by NBA.com for the upcoming regular season.
# Recorded here so STATUS/calendar agree; not a schedule ingest.
NEXT_REGULAR_SEASON_OPEN = date(2026, 10, 20)

FIRST_TRACKED_SEASON = 2002


@dataclass(frozen=True)
class SeasonLabel:
    """Season start-year label (for example 2025 for the 2025-26 season)."""

    season: int
    note: str = ""


def season_label_for_date(day: date) -> int:
    """Approximate NBA season label from calendar date.

    NBA seasons are labeled by the calendar year of opening tip (October).
    Dates in January through June belong to the prior season label. July
    through September are tagged with the upcoming season year.
    """

    if day.month >= 10:
        return day.year
    if day.month <= 6:
        return day.year - 1
    return day.year


def season_label_detail(day: date) -> SeasonLabel:
    """Season label plus a short resolution note (no invented slate weeks)."""

    season = season_label_for_date(day)
    if day.month >= 10 or day.month <= 6:
        return SeasonLabel(season=season, note="in_season_or_postseason_window")
    return SeasonLabel(season=season, note="offseason_upcoming_season_label")


def days_until_next_regular_open(day: date | None = None) -> int:
    """Whole days from ``day`` to ``NEXT_REGULAR_SEASON_OPEN`` (may be negative)."""

    as_of = day if day is not None else date.today()
    return (NEXT_REGULAR_SEASON_OPEN - as_of).days


def tracked_seasons(now: date | None = None) -> tuple[int, ...]:
    """Tracked season labels from 2002 through the current Eastern season label."""

    as_of = now if now is not None else date.today()
    return tuple(range(FIRST_TRACKED_SEASON, season_label_for_date(as_of) + 1))
