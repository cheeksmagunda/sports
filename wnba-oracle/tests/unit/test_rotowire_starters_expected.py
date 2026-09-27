"""When an empty RotoWire page is a real failure (#319, #441)."""

from __future__ import annotations

import datetime as dt
from unittest.mock import patch

from wnba_oracle.ingest.rotowire import starters_expected
from wnba_oracle.scheduler import job1

# 2026-09-27 18:00Z is 14:00 ET on 9/27, the #441 slate's first tip.
TIP = dt.datetime(2026, 9, 27, 18, 0, tzinfo=dt.UTC)


def _at(day: int, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(2026, 9, day, hour, minute, tzinfo=dt.UTC)


def test_day_before_inside_lead_is_not_expected() -> None:
    # #441: job1 at 13:09Z on 9/26 was 28.8h out, inside 30h but the day before.
    assert starters_expected(TIP, _at(26, 13, 9)) is False
    # job1late's last day-before fire, 23:35Z, is still 9/26 in Eastern time.
    assert starters_expected(TIP, _at(26, 23, 35)) is False


def test_tip_day_morning_is_expected() -> None:
    assert starters_expected(TIP, _at(27, 13, 0)) is True


def test_eastern_midnight_boundary_uses_slate_calendar() -> None:
    # 03:30Z on 9/27 is 23:30 ET on 9/26; 04:30Z is 00:30 ET on 9/27.
    assert starters_expected(TIP, _at(27, 3, 30)) is False
    assert starters_expected(TIP, _at(27, 4, 30)) is True


def test_outside_lead_is_not_expected() -> None:
    late_tip = dt.datetime(2026, 9, 28, 23, 0, tzinfo=dt.UTC)
    assert starters_expected(late_tip, _at(27, 13, 0)) is False


def test_after_tip_is_still_expected() -> None:
    assert starters_expected(TIP, _at(27, 20, 0)) is True


def test_naive_tip_is_treated_as_utc() -> None:
    assert starters_expected(TIP.replace(tzinfo=None), _at(27, 13, 0)) is True


def test_job1_near_tip_quiet_day_before_next_day_tip() -> None:
    with patch("wnba_oracle.scheduler.job2_io._load_slate_lock_time", return_value=TIP):
        assert job1._rotowire_near_tip("2026-09-26", now_utc=_at(26, 13, 9)) is False
        assert job1._rotowire_near_tip("2026-09-26", now_utc=_at(27, 13, 0)) is True


def test_job1_near_tip_unknown_tip_stays_quiet() -> None:
    with patch("wnba_oracle.scheduler.job2_io._load_slate_lock_time", return_value=None):
        assert job1._rotowire_near_tip("2026-09-26", now_utc=_at(27, 13, 0)) is False
