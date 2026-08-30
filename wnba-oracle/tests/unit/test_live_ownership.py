"""#38/F6: same-day live ownership capture gating and safety.

The capture itself (Playwright + live HTTP) is not exercised here -- it is
an explicit, timeout-bounded, opt-in side effect on job2's dispatch. What
must be pinned: the time-window gate (don't launch a browser for hours
before lock), and that nothing this module does can ever raise into job2.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import patch

import pytest

from wnba_oracle.scheduler import live_ownership as lo

LOCK = dt.datetime(2026, 8, 30, 18, 0, tzinfo=dt.UTC)


def test_skips_when_lock_time_unknown() -> None:
    assert lo.should_attempt_capture(now_utc=LOCK, lock_time=None) is False


def test_skips_well_before_lock() -> None:
    now = LOCK - dt.timedelta(hours=3)
    assert lo.should_attempt_capture(now_utc=now, lock_time=LOCK) is False


def test_attempts_within_window_before_lock() -> None:
    now = LOCK - dt.timedelta(minutes=10)
    assert lo.should_attempt_capture(now_utc=now, lock_time=LOCK) is True


def test_attempts_exactly_at_window_boundary() -> None:
    now = LOCK - lo.CAPTURE_WINDOW_BEFORE_LOCK
    assert lo.should_attempt_capture(now_utc=now, lock_time=LOCK) is True


def test_attempts_after_lock() -> None:
    now = LOCK + dt.timedelta(minutes=5)
    assert lo.should_attempt_capture(now_utc=now, lock_time=LOCK) is True


def test_safe_wrapper_is_noop_outside_window() -> None:
    with patch.object(lo, "_discover_and_capture") as discover:
        lo.capture_live_ownership_safe(now_utc=LOCK - dt.timedelta(hours=2), lock_time=LOCK)
    discover.assert_not_called()


def test_safe_wrapper_never_raises_on_exception() -> None:
    async def _boom() -> dict:
        raise RuntimeError("network exploded")

    with patch.object(lo, "_discover_and_capture", side_effect=_boom):
        lo.capture_live_ownership_safe(now_utc=LOCK, lock_time=LOCK)  # must not raise


def test_safe_wrapper_never_raises_on_timeout() -> None:
    async def _hang() -> dict:
        import asyncio

        await asyncio.sleep(10)
        return {"status": "should not get here"}

    with (
        patch.object(lo, "_discover_and_capture", side_effect=_hang),
        patch.object(lo, "CAPTURE_TIMEOUT_SECONDS", 0.01),
    ):
        lo.capture_live_ownership_safe(now_utc=LOCK, lock_time=LOCK)  # must not raise


def test_safe_wrapper_logs_successful_result() -> None:
    async def _ok() -> dict:
        return {"status": "captured", "contest_id": 2117, "n_players": 30}

    with (
        patch.object(lo, "_discover_and_capture", side_effect=_ok),
        patch.object(lo, "log") as log,
    ):
        lo.capture_live_ownership_safe(now_utc=LOCK, lock_time=LOCK)
    log.info.assert_called_once_with(
        "live_ownership_capture", status="captured", contest_id=2117, n_players=30
    )
