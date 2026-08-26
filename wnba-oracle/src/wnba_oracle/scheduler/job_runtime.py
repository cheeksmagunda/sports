"""WNBA-owned job registration and lifecycle hooks."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from oracle_core.jobs import (
    JobContext,
    JobLifecycleHook,
    JobRegistry,
    JobResult,
    JobSpec,
    JobStatus,
)
from sqlalchemy import text

from wnba_oracle.common.clock import slate_date as current_slate_date
from wnba_oracle.common.logging import StructuredLogger, get_logger
from wnba_oracle.common.settings import Settings
from wnba_oracle.db.engine import get_engine

PICKING_JOBS = frozenset({"job1", "job1games", "job1late", "job2"})
REALSPORTS_JOBS = frozenset({"job1", "job1games", "dayclose", "backfill"})
JOB_NAMES = ("job1", "job1games", "job1late", "job2", "dayclose", "backfill")


def _from_exit_code(job_name: str, exit_code: int) -> JobResult:
    if exit_code == 0:
        return JobResult.success(source_exit_code=exit_code)
    return JobResult.failed(
        f"{job_name} returned a nonzero exit code",
        source_exit_code=exit_code,
    )


def _with_realsports_access(
    context: JobContext,
    operation: Callable[[], JobResult],
) -> JobResult:
    from wnba_oracle.scheduler.realsports_access import run_with_access_window

    return run_with_access_window(context, operation)


def _handler(job_name: str, settings: Settings) -> Callable[[JobContext], JobResult]:
    def run(context: JobContext) -> JobResult:
        slate = str(context.metadata["slate_date"])
        if job_name in PICKING_JOBS and settings.picks_paused_on(current_slate_date()):
            context.logger.info(
                "picks_paused_skip",
                pause_start=settings.picks_pause_start,
                pause_end=settings.picks_pause_end,
            )
            return JobResult.skipped("picking is operator-paused", reason="picks_paused")

        if job_name == "job1":
            from wnba_oracle.scheduler import job1

            return _with_realsports_access(
                context,
                lambda: _from_exit_code(job_name, job1.main()),
            )
        if job_name == "job1games":
            from wnba_oracle.scheduler import job1

            def _run_game_starts() -> JobResult:
                job1.run_game_starts(slate)
                return JobResult.success()

            return _with_realsports_access(context, _run_game_starts)
        if job_name == "job1late":
            from wnba_oracle.scheduler import job1

            return _from_exit_code(job_name, job1.main_lite())
        if job_name == "job2":
            from wnba_oracle.scheduler import job2

            return _from_exit_code(job_name, job2.main())
        if job_name == "dayclose":
            from wnba_oracle.scheduler import job_dayclose

            return _with_realsports_access(context, job_dayclose.run)
        if job_name == "backfill":
            from wnba_oracle.scheduler import job_backfill

            return _with_realsports_access(
                context,
                lambda: _from_exit_code(job_name, job_backfill.main()),
            )
        return JobResult.failed("unregistered WNBA job")

    return run


def build_job_registry(settings: Settings) -> JobRegistry:
    """Register every stable WNBA cron name with the shared runner."""

    return JobRegistry(
        [
            JobSpec(name=name, handler=_handler(name, settings), roles=frozenset({name}))
            for name in JOB_NAMES
        ]
    )


class WatchdogLifecycleHook(JobLifecycleHook):
    """Run WNBA watchdog checks after the jobs that affect daily picks."""

    def __init__(self, logger: StructuredLogger | None = None) -> None:
        self.logger = logger or get_logger("oracle.cron.watchdog_hook")

    def on_start(self, context: JobContext) -> None:
        return None

    def on_complete(self, context: JobContext, result: JobResult) -> None:
        if context.job_name not in {"job1", "job2"}:
            return
        if result.status is JobStatus.SKIPPED and result.details.get("reason") == "picks_paused":
            return
        try:
            from wnba_oracle.scheduler.watchdog import run_watchdog

            run_watchdog(
                str(context.metadata["slate_date"]),
                check_config_drift=context.job_name == "job2",
            )
        except Exception as exc:
            self.logger.exception(
                "watchdog_failed",
                job=context.job_name,
                error_type=type(exc).__name__,
            )

    def on_error(self, context: JobContext, error: BaseException) -> None:
        return None


class PostgresJobRunHook(JobLifecycleHook):
    """Persist durable job heartbeats without affecting job outcomes."""

    def __init__(self, logger: StructuredLogger | None = None) -> None:
        self.logger = logger or get_logger("oracle.cron.job_runs")

    def _execute(self, statement: Any, params: dict[str, Any]) -> None:
        try:
            with get_engine().begin() as connection:
                connection.execute(statement, params)
        except Exception as exc:
            self.logger.warning(
                "job_run_heartbeat_failed",
                error_type=type(exc).__name__,
            )

    def on_start(self, context: JobContext) -> None:
        self._execute(
            text(
                "INSERT INTO job_runs "
                "(run_id, job_name, role, slate_date, status, started_at, details_json) "
                "VALUES (:run_id, :job_name, :role, :slate_date, 'running', "
                ":started_at, CAST(:details AS jsonb))"
            ),
            {
                "run_id": context.run_id,
                "job_name": context.job_name,
                "role": context.role,
                "slate_date": str(context.metadata["slate_date"]),
                "started_at": context.started_at,
                "details": json.dumps(dict(context.metadata), default=str),
            },
        )

    def on_complete(self, context: JobContext, result: JobResult) -> None:
        self._execute(
            text(
                "UPDATE job_runs SET status = :status, completed_at = :completed_at, "
                "exit_code = :exit_code, details_json = CAST(:details AS jsonb) "
                "WHERE run_id = :run_id"
            ),
            {
                "run_id": context.run_id,
                "status": result.status.value,
                "completed_at": context.now(),
                "exit_code": result.exit_code,
                "details": json.dumps(dict(result.details), default=str),
            },
        )

    def on_error(self, context: JobContext, error: BaseException) -> None:
        self._execute(
            text(
                "UPDATE job_runs SET status = 'failed', completed_at = :completed_at, "
                "exit_code = 1, details_json = CAST(:details AS jsonb) WHERE run_id = :run_id"
            ),
            {
                "run_id": context.run_id,
                "completed_at": context.now(),
                "details": json.dumps({"error_type": type(error).__name__}),
            },
        )
