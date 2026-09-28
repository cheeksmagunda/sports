"""Sunday multi-game and one-night must not share a label."""

from datetime import datetime
from zoneinfo import ZoneInfo

from nfl_oracle.replay.slate_regime import regime_from_kickoffs

ET = ZoneInfo("America/New_York")


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=ET)


def test_sunday_with_snf_stays_sunday_multi() -> None:
    kickoffs = (_at(27, 13), _at(27, 16, 25), _at(27, 20, 20))
    assert regime_from_kickoffs(kickoffs) == "sunday_multi"


def test_one_night_labels_are_not_sunday() -> None:
    assert regime_from_kickoffs((_at(24, 20, 15),)) == "one_night_tnf"
    assert regime_from_kickoffs((_at(27, 20, 20),)) == "one_night_snf"
    assert regime_from_kickoffs((_at(28, 20, 15),)) == "one_night_mnf"


def test_empty_kickoffs_are_unscheduled() -> None:
    assert regime_from_kickoffs(()) == "unscheduled"
