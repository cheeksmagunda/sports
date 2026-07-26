"""picks_paused_on / picks_resume_date: the operator-directed pause window."""

from __future__ import annotations

import datetime as dt

from wnba_oracle.common.settings import Settings


def _settings(start: str = "", end: str = "") -> Settings:
    return Settings(PICKS_PAUSE_START=start, PICKS_PAUSE_END=end)


def test_unset_never_paused() -> None:
    s = _settings()
    assert s.picks_paused_on(dt.date(2026, 7, 26)) is False
    assert s.picks_resume_date() is None


def test_paused_within_inclusive_range() -> None:
    s = _settings("2026-07-26", "2026-07-28")
    assert s.picks_paused_on(dt.date(2026, 7, 25)) is False
    assert s.picks_paused_on(dt.date(2026, 7, 26)) is True
    assert s.picks_paused_on(dt.date(2026, 7, 27)) is True
    assert s.picks_paused_on(dt.date(2026, 7, 28)) is True
    assert s.picks_paused_on(dt.date(2026, 7, 29)) is False


def test_resume_date_is_day_after_end() -> None:
    s = _settings("2026-07-26", "2026-07-28")
    assert s.picks_resume_date() == "2026-07-29"


def test_only_start_set_is_not_paused() -> None:
    s = _settings(start="2026-07-26")
    assert s.picks_paused_on(dt.date(2026, 7, 26)) is False
    assert s.picks_resume_date() is None


def test_malformed_dates_never_paused() -> None:
    s = _settings("not-a-date", "also-not-a-date")
    assert s.picks_paused_on(dt.date(2026, 7, 26)) is False
    assert s.picks_resume_date() is None
