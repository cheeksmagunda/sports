"""Worker failure rows use the Eastern slate date (#599)."""

from __future__ import annotations

from datetime import UTC, datetime

from nfl_oracle.recommendations.cli import (
    worker_failure_detail_code,
    worker_failure_slate_day,
)


def test_utc_midnight_stays_on_the_previous_eastern_slate() -> None:
    # 2026-09-28 00:20Z is still 2026-09-27 20:20 EDT.
    now = datetime(2026, 9, 28, 0, 20, tzinfo=UTC)
    assert worker_failure_slate_day(None, now).isoformat() == "2026-09-27"


def test_after_eastern_midnight_rolls_the_slate() -> None:
    # 2026-09-28 05:00Z is 2026-09-28 01:00 EDT.
    now = datetime(2026, 9, 28, 5, 0, tzinfo=UTC)
    assert worker_failure_slate_day(None, now).isoformat() == "2026-09-28"


def test_requested_day_wins_over_the_clock() -> None:
    now = datetime(2026, 9, 28, 0, 20, tzinfo=UTC)
    requested = worker_failure_slate_day(None, datetime(2026, 9, 29, 12, tzinfo=UTC))
    assert worker_failure_slate_day(requested, now) == requested


def test_naive_clock_is_treated_as_utc() -> None:
    now = datetime(2026, 9, 28, 0, 20)
    assert worker_failure_slate_day(None, now).isoformat() == "2026-09-27"


def test_oserror_detail_keeps_errno_and_drops_the_path() -> None:
    error = FileNotFoundError(2, "No such file", "/secret/storage_state.json")
    code = worker_failure_detail_code(error, retryable_reason="")
    assert code == "filenotfounderror:2"
    assert "storage_state" not in code
    assert "secret" not in code


def test_oserror_without_errno_is_the_type_name() -> None:
    error = OSError("provider timeout")
    assert worker_failure_detail_code(error, retryable_reason="") == "oserror"


def test_retryable_gate_code_wins_over_the_type_name() -> None:
    error = ValueError("stale_player")
    assert worker_failure_detail_code(error, retryable_reason="stale_player") == "stale_player"


def test_other_exceptions_stay_type_only() -> None:
    error = RuntimeError("https://web.realapp.com/token=secret")
    code = worker_failure_detail_code(error, retryable_reason="")
    assert code == "runtimeerror"
    assert "realapp" not in code
