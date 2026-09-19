"""WNBA ownership of Real Sports account-window policy.

Default-off (issue #230): REALSPORTS_ACCESS_COORDINATION_ENABLED must be set
to a truthy value before job_runtime actually gates any job on a window.
Landing the coordinator, its migration, and the wired-but-disabled call
sites in the same change as flipping the flag would be a live production
behavior and schedule change with no separate rollback step; this keeps
those two decisions apart. See wnba-oracle/AGENTS.md for the enable
decision and the known nfl-oracle-worker gap.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date, timedelta

from oracle_core.jobs import JobContext, JobResult

from wnba_oracle.db.engine import get_engine
from wnba_oracle.scheduler.access_coordination import (
    AccessPolicy,
    finish_access_window,
    try_acquire_access_window,
)

_DEFAULT_SCOPE = "realsports-paid-account"
_DEFAULT_MIN_INTERVAL_MINUTES = 180
_DEFAULT_MAX_WINDOWS_PER_DAY = 4
_DEFAULT_TIMEZONE = "America/Los_Angeles"


def coordination_enabled() -> bool:
    """Whether job_runtime should gate REALSPORTS_JOBS on an access window.

    Default off. Flipping this on is a production behavior change (a denied
    window returns a retryable failure instead of running the job) and
    requires the durable migration to be applied first.
    """

    return os.environ.get("REALSPORTS_ACCESS_COORDINATION_ENABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be at least 1")
    return value


def access_policy() -> AccessPolicy:
    """Return conservative, account-wide collection spacing guardrails."""

    return AccessPolicy(
        min_interval=timedelta(
            minutes=_positive_int(
                "REALSPORTS_MIN_ACCESS_INTERVAL_MINUTES",
                _DEFAULT_MIN_INTERVAL_MINUTES,
            )
        ),
        max_windows_per_day=_positive_int(
            "REALSPORTS_MAX_ACCESS_WINDOWS_PER_DAY",
            _DEFAULT_MAX_WINDOWS_PER_DAY,
        ),
        timezone=os.environ.get("REALSPORTS_ACCESS_TIMEZONE", "").strip() or _DEFAULT_TIMEZONE,
    )


def _scope() -> str:
    return os.environ.get("REALSPORTS_ACCESS_SCOPE", "").strip() or _DEFAULT_SCOPE


def run_with_access_window(
    context: JobContext,
    operation: Callable[[], JobResult],
) -> JobResult:
    """Run one provider-touching operation under the shared account budget.

    A no-op passthrough when coordination_enabled() is False: calls
    operation() directly with no database access, no lock, and no window
    recorded. This is what keeps landing the coordinator from being a live
    behavior change by itself.
    """

    if not coordination_enabled():
        return operation()

    engine = get_engine()
    grant = try_acquire_access_window(
        engine,
        scope=_scope(),
        consumer=f"wnba:{context.job_name}",
        policy=access_policy(),
        slate_date=date.fromisoformat(str(context.metadata["slate_date"])),
        now=context.now(),
    )
    if not grant.granted:
        next_eligible = (
            grant.next_eligible_at.isoformat() if grant.next_eligible_at is not None else None
        )
        context.logger.warning(
            "realsports_access_window_denied",
            reason=grant.reason,
            windows_today=grant.windows_today,
            next_eligible_at=next_eligible,
        )
        return JobResult.retryable_failure(
            "Real Sports account access window is not available",
            reason=f"realsports_{grant.reason}",
            windows_today=grant.windows_today,
            next_eligible_at=next_eligible,
        )

    assert grant.window_id is not None
    try:
        result = operation()
    except BaseException:
        finish_access_window(
            engine,
            grant.window_id,
            outcome="failed",
            completed_at=context.now(),
        )
        raise
    finish_access_window(
        engine,
        grant.window_id,
        outcome=result.status.value,
        completed_at=context.now(),
    )
    return result
