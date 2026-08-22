from __future__ import annotations

import datetime as dt

import pytest

from wnba_oracle.common.clock import slate_date


def test_overnight_utc_fire_stays_on_previous_eastern_slate() -> None:
    assert slate_date(dt.datetime(2026, 8, 20, 3, 59, tzinfo=dt.UTC)) == dt.date(2026, 8, 19)
    assert slate_date(dt.datetime(2026, 8, 20, 4, 0, tzinfo=dt.UTC)) == dt.date(2026, 8, 20)


def test_winter_boundary_tracks_standard_time() -> None:
    assert slate_date(dt.datetime(2026, 1, 20, 4, 59, tzinfo=dt.UTC)) == dt.date(2026, 1, 19)
    assert slate_date(dt.datetime(2026, 1, 20, 5, 0, tzinfo=dt.UTC)) == dt.date(2026, 1, 20)


def test_naive_instant_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        slate_date(dt.datetime(2026, 8, 20, 1, 0))
