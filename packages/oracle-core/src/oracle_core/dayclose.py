"""Generic day-close sweep orchestration, shared by every sport application.

A day-close job grades one frozen decision against finalized real-world
results, once those results exist. Provider finalization timing is not
always same-day, so every sport's day-close job needs the same shape: grade
a target day, then sweep backward through a bounded catch-up window for any
earlier day that has a decision but no grade yet (a later-finalizing
contest, a missed run, an earlier outage). This module owns only that
orchestration shape.

Sport-specific concerns stay in the owning application: what "graded" means,
what provider data to refresh, what a day's identity is, and which outcome
statuses are terminal versus worth flagging all live in the `close_one_day`
callback passed to `run_sweep`. This module never imports a sport package.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo

from oracle_core.jobs import JobResult, JobStatus


@dataclass(frozen=True)
class DayCloseOutcome:
    """One day's day-close attempt result.

    `status` is defined entirely by the owning application (for example
    "graded", "already_graded", "no_decision", "not_finalized"). Only this
    module's own "error" status, assigned when `close_one_day` raises, is
    reserved.
    """

    day: date
    status: str
    detail: str = ""


CloseOneDay = Callable[[date], DayCloseOutcome]


def default_target_day(now: datetime, tz: tzinfo) -> date:
    """Yesterday's date in `tz`, the common default day-close target."""

    return (now.astimezone(tz) - timedelta(days=1)).date()


def run_sweep(
    *,
    target_day: date,
    close_one_day: CloseOneDay,
    catchup_window_days: int = 7,
    settled_statuses: frozenset[str] = frozenset(),
) -> JobResult:
    """Attempt `target_day`, then sweep a bounded catch-up window backward.

    `close_one_day` must own its own idempotency: called again for a day
    that is already graded or has no decision to grade, it should return
    quickly without a costly provider refresh, and that status should be
    included in `settled_statuses` so this sweep does not report "degraded"
    for ordinary steady-state days. An uncaught exception from
    `close_one_day` is isolated to that one day (an "error" outcome) so it
    cannot prevent the sweep from covering the rest of the window.
    """

    if catchup_window_days < 1:
        raise ValueError("catchup_window_days must be at least 1")

    outcomes: dict[str, str] = {}
    details: dict[str, str] = {}

    def attempt(day: date) -> None:
        try:
            outcome = close_one_day(day)
        except Exception as error:  # noqa: BLE001 - isolate to this day, keep sweeping
            outcomes[day.isoformat()] = "error"
            details[day.isoformat()] = type(error).__name__
            return
        outcomes[outcome.day.isoformat()] = outcome.status
        if outcome.detail:
            details[outcome.day.isoformat()] = outcome.detail

    attempt(target_day)
    for offset in range(1, catchup_window_days):
        candidate = target_day - timedelta(days=offset)
        if candidate.isoformat() in outcomes:
            continue
        attempt(candidate)

    failed_days = [day for day, status in outcomes.items() if status == "error"]
    if failed_days:
        job_status = JobStatus.FAILED
    elif any(status not in settled_statuses for status in outcomes.values()):
        job_status = JobStatus.DEGRADED
    else:
        job_status = JobStatus.SUCCESS

    return JobResult(
        status=job_status,
        message=f"processed {target_day.isoformat()}",
        details={
            "processed_day": target_day.isoformat(),
            "outcomes": outcomes,
            "details": details,
        },
    )
