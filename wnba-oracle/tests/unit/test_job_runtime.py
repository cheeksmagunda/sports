"""WNBA registration, heartbeat, and dead-man surface tests."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from oracle_core.jobs import JobContext, JobResult

from wnba_oracle.api import watchdog_router
from wnba_oracle.common.logging import get_logger
from wnba_oracle.common.settings import Settings
from wnba_oracle.scheduler.job_runtime import JOB_NAMES, PostgresJobRunHook, build_job_registry


def test_registry_preserves_stable_cli_names_and_roles() -> None:
    registry = build_job_registry(Settings())

    assert registry.names() == tuple(sorted(JOB_NAMES))
    for name in JOB_NAMES:
        assert registry.get(name).roles == frozenset({name})


def test_postgres_hook_records_start_and_completion() -> None:
    connection = MagicMock()
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = connection
    now = dt.datetime(2026, 8, 20, 15, tzinfo=dt.UTC)
    context = JobContext(
        job_name="job2",
        role="job2",
        run_id="run-1",
        started_at=now,
        clock=lambda: now,
        logger=get_logger("test.job_runtime"),
        metadata={"slate_date": "2026-08-20"},
    )

    with patch("wnba_oracle.scheduler.job_runtime.get_engine", return_value=engine):
        hook = PostgresJobRunHook()
        hook.on_start(context)
        hook.on_complete(context, JobResult.success(frozen=True))

    assert connection.execute.call_count == 2
    start_params = connection.execute.call_args_list[0].args[1]
    complete_params = connection.execute.call_args_list[1].args[1]
    assert start_params["run_id"] == "run-1"
    assert start_params["slate_date"] == "2026-08-20"
    assert complete_params["status"] == "success"
    assert complete_params["exit_code"] == 0


def test_job_run_surface_includes_missing_jobs() -> None:
    started = dt.datetime(2026, 8, 20, 13, tzinfo=dt.UTC)
    row = SimpleNamespace(
        _mapping={
            "job_name": "job1",
            "role": "job1",
            "status": "success",
            "started_at": started,
            "completed_at": started + dt.timedelta(minutes=2),
            "exit_code": 0,
        }
    )
    connection = MagicMock()
    connection.execute.return_value = [row]
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection

    with patch.object(watchdog_router, "get_engine", return_value=engine):
        response = watchdog_router.get_job_runs_today()

    assert response["jobs"]["job1"]["status"] == "success"
    assert response["jobs"]["job2"] is None
    assert set(response["jobs"]) == set(JOB_NAMES)


def test_job_run_route_precedes_dynamic_watchdog_route() -> None:
    paths = [route.path for route in watchdog_router.router.routes]
    assert paths.index("/watchdog/jobs/today") < paths.index("/watchdog/{slate_date}")
