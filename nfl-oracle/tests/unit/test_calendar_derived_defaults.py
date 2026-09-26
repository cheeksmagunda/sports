from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from nfl_oracle.ingest.backfill import tracked_seasons
from nfl_oracle.valuelaw.candidates import eastern_today
from nfl_oracle.valuelaw.model import latest_two_seasons

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


@pytest.fixture()
def scripts_path() -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        yield
    finally:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))


def test_latest_two_seasons_resolves_from_dataset_rows() -> None:
    rows = [{"season": 2023}, {"season": 2025}, {"season": 2024}, {"season": 2025}]
    assert latest_two_seasons(rows) == (2024, 2025)


def test_latest_two_seasons_requires_two_labels() -> None:
    with pytest.raises(ValueError, match="need_at_least_two_seasons_in_dataset"):
        latest_two_seasons([{"season": 2025}])


def test_eastern_today_uses_us_eastern_calendar_date() -> None:
    # 2027-01-01 02:30 UTC is still 2026-12-31 in America/New_York.
    now = datetime(2027, 1, 1, 2, 30, tzinfo=ZoneInfo("UTC"))
    assert eastern_today(now=now) == date(2026, 12, 31)


def test_tracked_seasons_upper_bound_follows_calendar() -> None:
    assert tracked_seasons(as_of=date(2026, 9, 26))[-1] == 2026
    assert tracked_seasons(as_of=date(2026, 2, 1))[-1] == 2025
    assert tracked_seasons(as_of=date(2026, 9, 26))[0] == 2002


def test_cache_nflverse_season_max_default_is_calendar_derived(scripts_path: None) -> None:
    from cache_nflverse_schedules import default_season_max

    now = datetime(2027, 3, 15, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    assert default_season_max(now=now) == 2027
