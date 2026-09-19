from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import pytest
from oracle_core.jobs import JobContext, JobResult, JobStatus

from wnba_oracle.common.logging import get_logger
from wnba_oracle.scheduler import realsports_access
from wnba_oracle.scheduler.access_coordination import AccessGrant


def _context() -> JobContext:
    now = dt.datetime(2026, 9, 19, 16, tzinfo=dt.UTC)
    return JobContext(
        job_name="job1",
        role="job1",
        run_id="run-1",
        started_at=now,
        clock=lambda: now,
        logger=get_logger("test.realsports_access"),
        metadata={"slate_date": "2026-09-19"},
    )


def test_coordination_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REALSPORTS_ACCESS_COORDINATION_ENABLED", raising=False)
    assert realsports_access.coordination_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "True", "yes", "YES"])
def test_coordination_enabled_recognizes_truthy_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("REALSPORTS_ACCESS_COORDINATION_ENABLED", value)
    assert realsports_access.coordination_enabled() is True


def test_disabled_coordination_is_a_pure_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default-off state must never touch the database or the lock."""
    monkeypatch.delenv("REALSPORTS_ACCESS_COORDINATION_ENABLED", raising=False)
    operation = MagicMock(return_value=JobResult.success())

    with (
        patch.object(realsports_access, "get_engine") as get_engine,
        patch.object(realsports_access, "try_acquire_access_window") as acquire,
    ):
        result = realsports_access.run_with_access_window(_context(), operation)

    operation.assert_called_once()
    get_engine.assert_not_called()
    acquire.assert_not_called()
    assert result.status is JobStatus.SUCCESS


def test_policy_defaults_are_conservative(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "REALSPORTS_MIN_ACCESS_INTERVAL_MINUTES",
        "REALSPORTS_MAX_ACCESS_WINDOWS_PER_DAY",
        "REALSPORTS_ACCESS_TIMEZONE",
    ):
        monkeypatch.delenv(name, raising=False)

    policy = realsports_access.access_policy()

    assert policy.min_interval == dt.timedelta(hours=3)
    assert policy.max_windows_per_day == 4
    assert policy.timezone == "America/Los_Angeles"


def test_denied_window_never_runs_provider_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REALSPORTS_ACCESS_COORDINATION_ENABLED", "1")
    operation = MagicMock(return_value=JobResult.success())
    denied = AccessGrant(
        granted=False,
        reason="cooldown",
        next_eligible_at=dt.datetime(2026, 9, 19, 18, tzinfo=dt.UTC),
        windows_today=2,
    )

    with (
        patch.object(realsports_access, "get_engine", return_value=MagicMock()),
        patch.object(realsports_access, "try_acquire_access_window", return_value=denied),
    ):
        result = realsports_access.run_with_access_window(_context(), operation)

    operation.assert_not_called()
    assert result.status is JobStatus.RETRYABLE_FAILURE
    assert result.details["reason"] == "realsports_cooldown"


def test_granted_window_records_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REALSPORTS_ACCESS_COORDINATION_ENABLED", "1")
    engine = MagicMock()
    granted = AccessGrant(True, "granted", window_id=17, windows_today=1)

    with (
        patch.object(realsports_access, "get_engine", return_value=engine),
        patch.object(realsports_access, "try_acquire_access_window", return_value=granted),
        patch.object(realsports_access, "finish_access_window") as finish,
    ):
        result = realsports_access.run_with_access_window(
            _context(),
            lambda: JobResult.success(rows=60),
        )

    assert result.status is JobStatus.SUCCESS
    finish.assert_called_once()
    assert finish.call_args.kwargs["outcome"] == "success"


def test_failed_operation_still_consumes_and_closes_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALSPORTS_ACCESS_COORDINATION_ENABLED", "1")
    engine = MagicMock()
    granted = AccessGrant(True, "granted", window_id=19, windows_today=1)

    def _raise() -> JobResult:
        raise RuntimeError("provider failed")

    with (
        patch.object(realsports_access, "get_engine", return_value=engine),
        patch.object(realsports_access, "try_acquire_access_window", return_value=granted),
        patch.object(realsports_access, "finish_access_window") as finish,
        pytest.raises(RuntimeError, match="provider failed"),
    ):
        realsports_access.run_with_access_window(_context(), _raise)

    finish.assert_called_once()
    assert finish.call_args.kwargs["outcome"] == "failed"
