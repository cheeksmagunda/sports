"""Tests for the durable Job 1 pre-freeze evidence check."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import ModuleType

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
