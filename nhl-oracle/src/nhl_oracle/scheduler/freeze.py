"""NHL freeze-cycle job skeleton.

Fixes the step order in code before any real collect() exists to call:
collect, then read the decision clock, then load context, then check model
freshness, then prepare, then publish. This structurally prevents NFL's
clock-ordering bug (commit 241201a), where decision_at was captured before
collect() and every downstream freshness check therefore saw "future
evidence" and failed forever. No live provider, model, or optimizer is wired
here; every step is an injected callable so this skeleton is exercisable on
its own before Week 2/3 build those pieces out.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from oracle_core.jobs import JobContext, JobResult, JobSpec

DEFAULT_LEASE_KEY = "nhl:freeze_cycle"
DEFAULT_LEASE_TTL_SECONDS = 300


@dataclass(frozen=True)
class FreezeCycleRecord:
    """What happened during one freeze-cycle attempt, and when."""

    decision_at: datetime
    collected: bool
    context_loaded: bool
    model_fresh: bool
    prepared: bool
    published: bool
    contest_entry: bool


def run_freeze_cycle(
    context: JobContext,
    *,
    collect: Callable[[], None],
    load_context: Callable[[], None] | None = None,
    ensure_model_fresh: Callable[[], bool] | None = None,
    prepare: Callable[[], bool] | None = None,
    publish: Callable[[], bool] | None = None,
) -> tuple[JobResult, FreezeCycleRecord]:
    """Run one freeze cycle in the fixed step order; return (result, record)."""

    collect()
    decision_at = context.now()

    if load_context is not None:
        load_context()

    model_fresh = True if ensure_model_fresh is None else ensure_model_fresh()
    if not model_fresh:
        record = FreezeCycleRecord(
            decision_at=decision_at,
            collected=True,
            context_loaded=True,
            model_fresh=False,
            prepared=False,
            published=False,
            contest_entry=False,
        )
        return (
            JobResult.retryable_failure("model_not_fresh", decision_at=decision_at.isoformat()),
            record,
        )

    prepared = True if prepare is None else prepare()
    if not prepared:
        record = FreezeCycleRecord(
            decision_at=decision_at,
            collected=True,
            context_loaded=True,
            model_fresh=True,
            prepared=False,
            published=False,
            contest_entry=False,
        )
        return (
            JobResult.retryable_failure("prepare_failed", decision_at=decision_at.isoformat()),
            record,
        )

    published = True if publish is None else publish()
    record = FreezeCycleRecord(
        decision_at=decision_at,
        collected=True,
        context_loaded=True,
        model_fresh=True,
        prepared=True,
        published=published,
        contest_entry=False,
    )
    if published:
        result = JobResult.success("freeze_cycle_complete", decision_at=decision_at.isoformat())
    else:
        result = JobResult.retryable_failure("publish_failed", decision_at=decision_at.isoformat())
    return result, record


def build_freeze_job(
    *,
    collect: Callable[[], None],
    load_context: Callable[[], None] | None = None,
    ensure_model_fresh: Callable[[], bool] | None = None,
    prepare: Callable[[], bool] | None = None,
    publish: Callable[[], bool] | None = None,
    lease_key: str = DEFAULT_LEASE_KEY,
    lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
) -> JobSpec:
    """Build a JobSpec wiring run_freeze_cycle behind a single-active-writer lease."""

    def handler(context: JobContext) -> JobResult:
        result, _record = run_freeze_cycle(
            context,
            collect=collect,
            load_context=load_context,
            ensure_model_fresh=ensure_model_fresh,
            prepare=prepare,
            publish=publish,
        )
        return result

    return JobSpec(
        name="nhl_freeze_cycle",
        handler=handler,
        lease_key=lease_key,
        lease_ttl_seconds=lease_ttl_seconds,
    )
