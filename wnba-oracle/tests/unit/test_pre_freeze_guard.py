"""Tests for the durable Job 1 pre-freeze evidence check."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import ModuleType

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts"


def _load_guard() -> ModuleType:
    common_spec = importlib.util.spec_from_file_location(
        "ops_common", SCRIPTS_DIR / "ops_common.py"
    )
    assert common_spec is not None
    assert common_spec.loader is not None
    common = importlib.util.module_from_spec(common_spec)
    sys.modules[common_spec.name] = common
    common_spec.loader.exec_module(common)

    guard_spec = importlib.util.spec_from_file_location(
        "pre_freeze_guard", SCRIPTS_DIR / "pre_freeze_guard.py"
    )
    assert guard_spec is not None
    assert guard_spec.loader is not None
    guard = importlib.util.module_from_spec(guard_spec)
    sys.modules[guard_spec.name] = guard
    guard_spec.loader.exec_module(guard)
    return guard


def _window(guard: ModuleType):
    return guard.RunWindow.from_strings(
        role="job1",
        slate_date="2026-08-20",
        started_at="2026-08-20T13:00:00Z",
        ended_at="2026-08-20T13:10:00Z",
    )


def _payload(*, slate_date: str = "2026-08-20", started_at: str = "2026-08-20T13:01:00Z"):
    return {
        "slate_date": slate_date,
        "jobs": {
            "job1": {
                "role": "job1",
                "status": "success",
                "started_at": started_at,
                "completed_at": "2026-08-20T13:05:00Z",
                "exit_code": 0,
            }
        },
    }


def test_durable_job1_record_in_window_is_accepted() -> None:
    guard = _load_guard()

    check = guard._job1_durable_run_check(_payload(), window=_window(guard))

    assert check.status == "ok"


def test_durable_job1_record_rejects_wrong_slate_date() -> None:
    guard = _load_guard()

    check = guard._job1_durable_run_check(
        _payload(slate_date="2026-08-19"),
        window=_window(guard),
    )

    assert check.status == "alert"
    assert "wrong slate date" in check.summary


def test_durable_job1_record_rejects_early_run() -> None:
    guard = _load_guard()

    check = guard._job1_durable_run_check(
        _payload(started_at="2026-08-20T12:50:00Z"),
        window=_window(guard),
    )

    assert check.status == "alert"
    assert "outside the requested window" in check.summary


def _job_runs_ok() -> dict[str, object]:
    return _payload()


def _watchdog_body(
    *,
    events: list[dict[str, str]] | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "slate_date": "2026-08-20",
        "events": events or [],
        "history": history or [],
    }


def _install_api_mocks(
    guard: ModuleType, monkeypatch: pytest.MonkeyPatch, *, watchdog: dict
) -> None:
    slate_date = "2026-08-20"

    def get_json(url: str):
        if url.endswith("/health"):
            return 200, {"status": "ok"}
        if url.endswith(f"/watchdog/{slate_date}?severity_min=warn"):
            return 200, watchdog
        if url.endswith("/watchdog/jobs/today"):
            return 200, _job_runs_ok()
        if url.endswith(f"/slate/{slate_date}"):
            return 404, {}
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(guard, "get_json", get_json)


def _pipeline_watchdog_check(guard: ModuleType, monkeypatch: pytest.MonkeyPatch, *, watchdog: dict):
    _install_api_mocks(guard, monkeypatch, watchdog=watchdog)
    checks, _health_failed = guard._api_checks(
        "https://api.example",
        "2026-08-20",
        window=_window(guard),
    )
    return next(check for check in checks if check.name == "Pipeline watchdog")


@pytest.mark.parametrize(
    "trigger",
    ["model_artifact_unset", "model_artifact_unresolved"],
)
def test_pipeline_watchdog_alerts_on_model_artifact_hard_trigger_in_history_only(
    monkeypatch: pytest.MonkeyPatch,
    trigger: str,
) -> None:
    """Live /watchdog omits model_artifact_* (#331); cron history must still fail closed."""
    guard = _load_guard()

    check = _pipeline_watchdog_check(
        guard,
        monkeypatch,
        watchdog=_watchdog_body(history=[{"trigger": trigger}]),
    )

    assert check.status == "alert"
    assert trigger in check.summary


def test_pipeline_watchdog_unions_live_events_and_cron_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = _load_guard()

    check = _pipeline_watchdog_check(
        guard,
        monkeypatch,
        watchdog=_watchdog_body(
            events=[{"trigger": "config_drift"}],
            history=[{"trigger": "model_artifact_unset"}],
        ),
    )

    assert check.status == "alert"
    assert "model_artifact_unset" in check.summary
    assert "config_drift" not in check.summary


def test_pipeline_watchdog_warns_on_advisory_trigger_in_history_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = _load_guard()

    check = _pipeline_watchdog_check(
        guard,
        monkeypatch,
        watchdog=_watchdog_body(history=[{"trigger": "config_drift"}]),
    )

    assert check.status == "warn"
    assert "config_drift" in check.summary


def test_pipeline_watchdog_ok_when_live_and_history_are_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = _load_guard()

    check = _pipeline_watchdog_check(guard, monkeypatch, watchdog=_watchdog_body())

    assert check.status == "ok"
