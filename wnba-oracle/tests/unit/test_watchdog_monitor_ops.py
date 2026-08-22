"""Schedule-aware tests for the independent production monitor."""

from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import sys
from types import ModuleType

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts"


def _load_monitor() -> ModuleType:
    common_spec = importlib.util.spec_from_file_location(
        "ops_common", SCRIPTS_DIR / "ops_common.py"
    )
    assert common_spec is not None
    assert common_spec.loader is not None
    common = importlib.util.module_from_spec(common_spec)
    sys.modules[common_spec.name] = common
    common_spec.loader.exec_module(common)

    monitor_spec = importlib.util.spec_from_file_location(
        "watchdog_monitor", SCRIPTS_DIR / "watchdog_monitor.py"
    )
    assert monitor_spec is not None
    assert monitor_spec.loader is not None
    monitor = importlib.util.module_from_spec(monitor_spec)
    sys.modules[monitor_spec.name] = monitor
    monitor_spec.loader.exec_module(monitor)
    return monitor


def _payload(now: dt.datetime, jobs: dict[str, object]) -> dict[str, object]:
    return {
        "slate_date": "2026-08-20",
        "checked_at_utc": now.isoformat(),
        "jobs": jobs,
    }


def _successful_run(job_name: str, completed_at: dt.datetime) -> dict[str, object]:
    return {
        "role": job_name,
        "status": "success",
        "started_at": (completed_at - dt.timedelta(minutes=2)).isoformat(),
        "completed_at": completed_at.isoformat(),
        "exit_code": 0,
    }


def test_missing_runs_are_not_alerts_before_their_deadlines() -> None:
    monitor = _load_monitor()
    now = dt.datetime(2026, 8, 20, 5, tzinfo=dt.UTC)

    checks = monitor.job_deadline_checks(_payload(now, {}), now=now)

    assert len(checks) == 4
    assert {check.status for check in checks} == {"ok"}


def test_missing_runs_fail_closed_after_their_deadlines() -> None:
    monitor = _load_monitor()
    now = dt.datetime(2026, 8, 20, 17, tzinfo=dt.UTC)

    checks = monitor.job_deadline_checks(_payload(now, {}), now=now)

    assert {check.name for check in checks if check.status == "alert"} == {
        "Scheduled dayclose",
        "Scheduled job1",
        "Scheduled job1late",
        "Scheduled job2",
    }


def test_completed_jobs_satisfy_daily_and_recurring_windows() -> None:
    monitor = _load_monitor()
    now = dt.datetime(2026, 8, 20, 17, tzinfo=dt.UTC)
    jobs = {
        "dayclose": _successful_run("dayclose", now.replace(hour=6, minute=5)),
        "job1": _successful_run("job1", now.replace(hour=13, minute=5)),
        "job1late": _successful_run("job1late", now.replace(hour=16, minute=35)),
        "job2": _successful_run("job2", now.replace(hour=16, minute=55)),
    }

    checks = monitor.job_deadline_checks(_payload(now, jobs), now=now)

    assert {check.status for check in checks} == {"ok"}


def test_stale_recurring_completion_is_an_alert() -> None:
    monitor = _load_monitor()
    now = dt.datetime(2026, 8, 20, 17, tzinfo=dt.UTC)
    jobs = {
        "dayclose": _successful_run("dayclose", now.replace(hour=6)),
        "job1": _successful_run("job1", now.replace(hour=13)),
        "job1late": _successful_run("job1late", now.replace(hour=16, minute=35)),
        "job2": _successful_run("job2", now.replace(hour=16, minute=20)),
    }

    checks = monitor.job_deadline_checks(_payload(now, jobs), now=now)

    job2 = next(check for check in checks if check.name == "Scheduled job2")
    assert job2.status == "alert"
    assert "recurrence" in job2.summary


def test_early_same_slate_run_does_not_mask_a_missed_scheduled_fire() -> None:
    monitor = _load_monitor()
    now = dt.datetime(2026, 8, 20, 14, tzinfo=dt.UTC)
    jobs = {
        "dayclose": _successful_run("dayclose", dt.datetime(2026, 8, 20, 6, 5, tzinfo=dt.UTC)),
        "job1": _successful_run("job1", dt.datetime(2026, 8, 20, 10, 5, tzinfo=dt.UTC)),
    }

    checks = monitor.job_deadline_checks(_payload(now, jobs), now=now)

    job1 = next(check for check in checks if check.name == "Scheduled job1")
    assert job1.status == "alert"
    assert "schedule window" in job1.summary


def test_wrong_eastern_slate_date_fails_closed() -> None:
    monitor = _load_monitor()
    now = dt.datetime(2026, 8, 20, 17, tzinfo=dt.UTC)
    payload = _payload(now, {})
    payload["slate_date"] = "2026-08-19"

    checks = monitor.job_deadline_checks(payload, now=now)

    assert len(checks) == 1
    assert checks[0].status == "alert"
    assert "wrong WNBA slate date" in checks[0].summary


def test_recurring_freshness_does_not_alert_before_first_deadline() -> None:
    monitor = _load_monitor()
    now = dt.datetime(2026, 8, 20, 14, 5, tzinfo=dt.UTC)
    jobs = {
        "dayclose": _successful_run("dayclose", now.replace(hour=6)),
        "job1": _successful_run("job1", now.replace(hour=13)),
        "job2": _successful_run("job2", now.replace(hour=12)),
    }

    checks = monitor.job_deadline_checks(_payload(now, jobs), now=now)

    job2 = next(check for check in checks if check.name == "Scheduled job2")
    assert job2.status == "ok"


def test_monitor_consumes_job_endpoint_and_withholds_heartbeat_on_missing_rows(
    monkeypatch,
) -> None:
    monitor = _load_monitor()
    now = dt.datetime(2026, 8, 20, 17, tzinfo=dt.UTC)
    requested: list[str] = []

    def get_json(url: str):
        requested.append(url)
        if url.endswith("/health"):
            return 200, {"status": "ok"}
        if url.endswith("/watchdog/jobs/today"):
            return 200, _payload(now, {})
        return 200, {"slate_date": "2026-08-20", "events": []}

    heartbeat_calls: list[str] = []
    monkeypatch.setattr(monitor, "get_json", get_json)
    monkeypatch.setattr(monitor, "post_heartbeat", heartbeat_calls.append)

    checks = monitor.run("https://wnba.example", heartbeat_url="https://heartbeat", now=now)

    assert "https://wnba.example/watchdog/jobs/today" in requested
    assert any(check.status == "alert" for check in checks)
    assert heartbeat_calls == []


def test_monitor_withholds_heartbeat_and_recovery_while_a_job_is_running(
    monkeypatch,
) -> None:
    monitor = _load_monitor()
    now = dt.datetime(2026, 8, 20, 13, 40, tzinfo=dt.UTC)
    running = {
        "role": "job1",
        "status": "running",
        "started_at": (now - dt.timedelta(minutes=2)).isoformat(),
        "completed_at": None,
        "exit_code": None,
    }

    def get_json(url: str):
        if url.endswith("/health"):
            return 200, {"status": "ok"}
        if url.endswith("/watchdog/jobs/today"):
            return 200, _payload(
                now,
                {
                    "dayclose": _successful_run("dayclose", now.replace(hour=6, minute=5)),
                    "job1": running,
                },
            )
        return 200, {"slate_date": "2026-08-20", "events": []}

    heartbeat_calls: list[str] = []
    monkeypatch.setattr(monitor, "get_json", get_json)
    monkeypatch.setattr(monitor, "post_heartbeat", heartbeat_calls.append)

    checks = monitor.run("https://wnba.example", heartbeat_url="https://heartbeat", now=now)

    assert any(check.status == "warn" for check in checks)
    assert heartbeat_calls == []
    assert monitor.summarize_status(checks) == "warn"
