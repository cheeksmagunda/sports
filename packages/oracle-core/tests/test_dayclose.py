from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from oracle_core.dayclose import DayCloseOutcome, default_target_day, run_sweep
from oracle_core.jobs import JobStatus

SETTLED = frozenset({"graded", "already_graded", "no_decision"})


def test_default_target_day_is_yesterday_in_the_given_timezone() -> None:
    eastern = ZoneInfo("America/New_York")
    now = datetime(2026, 1, 2, 3, 0, tzinfo=UTC)  # 2026-01-01 22:00 in US/Eastern
    assert default_target_day(now, eastern) == date(2025, 12, 31)


def test_sweep_settles_on_the_target_day_alone() -> None:
    def close_one_day(day: date) -> DayCloseOutcome:
        assert day == date(2026, 1, 5)
        return DayCloseOutcome(day, "graded")

    result = run_sweep(
        target_day=date(2026, 1, 5),
        close_one_day=close_one_day,
        catchup_window_days=1,
        settled_statuses=SETTLED,
    )

    assert result.status == JobStatus.SUCCESS
    assert result.details["outcomes"] == {"2026-01-05": "graded"}


def test_sweep_retries_an_earlier_ungraded_day_within_the_window() -> None:
    attempted: list[date] = []

    def close_one_day(day: date) -> DayCloseOutcome:
        attempted.append(day)
        if day == date(2026, 1, 5):
            return DayCloseOutcome(day, "no_decision")
        if day == date(2026, 1, 2):
            return DayCloseOutcome(day, "graded")
        return DayCloseOutcome(day, "no_decision")

    result = run_sweep(
        target_day=date(2026, 1, 5),
        close_one_day=close_one_day,
        catchup_window_days=7,
        settled_statuses=SETTLED,
    )

    # Every day in the window is attempted, oldest reached last.
    assert attempted == [date(2026, 1, 5) - timedelta(days=offset) for offset in range(7)]
    assert result.status == JobStatus.SUCCESS
    assert result.details["outcomes"]["2026-01-02"] == "graded"


def test_sweep_reports_degraded_for_an_unsettled_status() -> None:
    def close_one_day(day: date) -> DayCloseOutcome:
        if day == date(2026, 1, 5):
            return DayCloseOutcome(day, "not_finalized")
        return DayCloseOutcome(day, "no_decision")

    result = run_sweep(
        target_day=date(2026, 1, 5),
        close_one_day=close_one_day,
        catchup_window_days=3,
        settled_statuses=SETTLED,
    )

    assert result.status == JobStatus.DEGRADED


def test_sweep_isolates_one_days_exception_and_reports_failed() -> None:
    def close_one_day(day: date) -> DayCloseOutcome:
        if day == date(2026, 1, 5):
            raise RuntimeError("provider unreachable")
        return DayCloseOutcome(day, "graded")

    result = run_sweep(
        target_day=date(2026, 1, 5),
        close_one_day=close_one_day,
        catchup_window_days=3,
        settled_statuses=SETTLED,
    )

    assert result.status == JobStatus.FAILED
    assert result.details["outcomes"]["2026-01-05"] == "error"
    assert result.details["details"]["2026-01-05"] == "RuntimeError"
    # The rest of the window still ran despite the one exception.
    assert result.details["outcomes"]["2026-01-04"] == "graded"
    assert result.details["outcomes"]["2026-01-03"] == "graded"


def test_sweep_rejects_a_non_positive_window() -> None:
    with pytest.raises(ValueError, match="catchup_window_days"):
        run_sweep(
            target_day=date(2026, 1, 5),
            close_one_day=lambda day: DayCloseOutcome(day, "graded"),
            catchup_window_days=0,
        )
