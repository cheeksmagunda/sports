from __future__ import annotations

from datetime import UTC, datetime, timedelta

from oracle_core.jobs import JobContext, JobRegistry, JobRunner, JobStatus
from oracle_core.logging import get_logger
from oracle_core.testing import FakeLeaseStore, FixedClock

from nhl_oracle.scheduler.freeze import build_freeze_job, run_freeze_cycle


def _context(clock: FixedClock) -> JobContext:
    return JobContext(
        job_name="nhl_freeze_cycle",
        role="worker",
        run_id="test-run",
        started_at=clock(),
        clock=clock,
        logger=get_logger("nhl_oracle.test"),
    )


def test_decision_at_is_read_after_collect_returns() -> None:
    start = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    clock = FixedClock(start)
    context = _context(clock)

    def collect() -> None:
        clock.advance(timedelta(minutes=5))

    result, record = run_freeze_cycle(context, collect=collect)

    assert record.decision_at == start + timedelta(minutes=5)
    assert record.collected is True
    assert record.contest_entry is False
    assert result.status == JobStatus.SUCCESS


def test_model_not_fresh_short_circuits_before_prepare_and_publish() -> None:
    start = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    clock = FixedClock(start)
    context = _context(clock)
    prepare_calls: list[bool] = []

    def prepare() -> bool:
        prepare_calls.append(True)
        return True

    result, record = run_freeze_cycle(
        context,
        collect=lambda: None,
        ensure_model_fresh=lambda: False,
        prepare=prepare,
    )

    assert record.model_fresh is False
    assert record.prepared is False
    assert prepare_calls == []
    assert result.status == JobStatus.RETRYABLE_FAILURE


def test_prepare_failure_short_circuits_before_publish() -> None:
    start = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    clock = FixedClock(start)
    context = _context(clock)
    publish_calls: list[bool] = []

    def publish() -> bool:
        publish_calls.append(True)
        return True

    result, record = run_freeze_cycle(
        context,
        collect=lambda: None,
        prepare=lambda: False,
        publish=publish,
    )

    assert record.prepared is False
    assert record.published is False
    assert publish_calls == []
    assert result.status == JobStatus.RETRYABLE_FAILURE


def test_freeze_job_is_skipped_when_lease_already_held() -> None:
    start = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    clock = FixedClock(start)
    lease_store = FakeLeaseStore(clock=lambda: clock().timestamp())
    held = lease_store.acquire("nhl:freeze_cycle", ttl_seconds=300)
    assert held is not None

    job = build_freeze_job(collect=lambda: None, lease_key="nhl:freeze_cycle")
    registry = JobRegistry([job])
    runner = JobRunner(registry, lease_store=lease_store, clock=clock)

    result = runner.run("nhl_freeze_cycle", role="worker")
    assert result.status == JobStatus.SKIPPED


def test_freeze_job_runs_when_lease_is_free() -> None:
    start = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    clock = FixedClock(start)
    lease_store = FakeLeaseStore(clock=lambda: clock().timestamp())

    job = build_freeze_job(collect=lambda: None, lease_key="nhl:freeze_cycle")
    registry = JobRegistry([job])
    runner = JobRunner(registry, lease_store=lease_store, clock=clock)

    result = runner.run("nhl_freeze_cycle", role="worker")
    assert result.status == JobStatus.SUCCESS
