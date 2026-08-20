from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from oracle_core.jobs import (
    JobContext,
    JobExitCode,
    JobRegistry,
    JobResult,
    JobRunner,
    JobSpec,
    JobStatus,
    RoleMismatchError,
    validate_role,
)
from oracle_core.testing import FakeLeaseStore, FixedClock, capture_json_logs


def test_job_result_exit_codes_are_stable() -> None:
    assert JobResult.success().exit_code == JobExitCode.SUCCESS
    assert JobResult.skipped().exit_code == JobExitCode.SUCCESS
    assert JobResult.degraded().exit_code == JobExitCode.DEGRADED
    assert JobResult.retryable_failure().exit_code == JobExitCode.RETRYABLE
    assert JobResult.failed().exit_code == JobExitCode.FAILURE


def test_registry_and_role_validation() -> None:
    spec = JobSpec("refresh", lambda _context: None, roles=frozenset({"worker"}))
    registry = JobRegistry([spec])

    assert registry.names() == ("refresh",)
    assert registry.get("refresh") is spec
    validate_role(spec, "worker")
    with pytest.raises(RoleMismatchError):
        validate_role(spec, "api")
    with pytest.raises(ValueError, match="already registered"):
        registry.register(spec)
    with pytest.raises(KeyError, match="Unknown job"):
        registry.get("missing")
    with pytest.raises(ValueError):
        JobSpec("Not Valid", lambda _context: None)


@dataclass
class RecordingHook:
    events: list[str] = field(default_factory=list)

    def on_start(self, context: JobContext) -> None:
        self.events.append(f"start:{context.job_name}")

    def on_complete(self, context: JobContext, result: JobResult) -> None:
        self.events.append(f"complete:{result.status.value}")

    def on_error(self, context: JobContext, error: BaseException) -> None:
        self.events.append(f"error:{type(error).__name__}")


def test_runner_injects_context_hooks_logs_and_owned_lease() -> None:
    clock = FixedClock(datetime(2026, 8, 20, 12, tzinfo=UTC))
    leases = FakeLeaseStore()
    hook = RecordingHook()

    def run(context: JobContext) -> JobResult:
        assert context.role == "worker"
        assert context.metadata == {"source": "spec", "request": "manual"}
        assert context.lease is not None
        clock.advance(timedelta(seconds=2))
        return JobResult.success("done", records=4)

    registry = JobRegistry(
        [
            JobSpec(
                "refresh",
                run,
                roles=frozenset({"worker"}),
                lease_key="refresh",
                lease_ttl_seconds=30,
                metadata={"source": "spec"},
            )
        ]
    )
    runner = JobRunner(registry, lease_store=leases, clock=clock, hooks=[hook])

    with capture_json_logs() as captured:
        result = runner.run("refresh", role="worker", metadata={"request": "manual"})

    assert result.status == JobStatus.SUCCESS
    assert result.details == {"records": 4}
    assert hook.events == ["start:refresh", "complete:success"]
    assert leases.leases == {}
    assert [event["message"] for event in captured.events] == ["job_started", "job_completed"]
    assert captured.events[-1]["duration_seconds"] == 2


def test_runner_skips_when_lease_is_held() -> None:
    leases = FakeLeaseStore()
    assert leases.acquire("refresh", ttl_seconds=30) is not None
    called = False

    def run(_context: JobContext) -> None:
        nonlocal called
        called = True

    runner = JobRunner(
        JobRegistry([JobSpec("refresh", run, lease_key="refresh")]), lease_store=leases
    )
    result = runner.run("refresh", role="worker")

    assert result.status == JobStatus.SKIPPED
    assert result.exit_code == 0
    assert not called


def test_runner_converts_exception_to_failure_without_secret_output() -> None:
    hook = RecordingHook()

    def fail(_context: JobContext) -> JobResult:
        raise RuntimeError("GET https://host.test/?token=do-not-log")

    runner = JobRunner(JobRegistry([JobSpec("broken", fail)]), hooks=[hook])
    with capture_json_logs() as captured:
        result = runner.run("broken", role="worker")

    assert result == JobResult.failed("job raised an exception", error_type="RuntimeError")
    assert hook.events == ["start:broken", "error:RuntimeError", "complete:failed"]
    assert "do-not-log" not in captured.stream.getvalue()


def test_runner_requires_lease_store_and_has_usage_exit_codes() -> None:
    spec = JobSpec("leased", lambda _context: None, lease_key="leased")
    runner = JobRunner(JobRegistry([spec]))

    with pytest.raises(RuntimeError, match="requires a lease store"):
        runner.run("leased", role="worker")
    assert runner.run_exit_code("missing", role="worker") == JobExitCode.USAGE

    restricted = JobRunner(
        JobRegistry([JobSpec("restricted", lambda _context: None, roles=frozenset({"special"}))])
    )
    assert restricted.run_exit_code("restricted", role="wrong") == JobExitCode.USAGE


def test_job_handler_must_return_supported_type() -> None:
    def invalid(_context: JobContext) -> object:
        return object()

    runner = JobRunner(JobRegistry([JobSpec("invalid", invalid)]))  # type: ignore[arg-type]

    assert runner.run("invalid", role="worker").status == JobStatus.FAILED
