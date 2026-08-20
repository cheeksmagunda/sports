#!/usr/bin/env python3
"""Probe WNBA API health, durable job runs, and the freeze watchdog."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
from collections.abc import Mapping
from zoneinfo import ZoneInfo

from ops_common import (
    Check,
    SafeRequestError,
    append_github_output,
    get_json,
    parse_timestamp,
    post_heartbeat,
    summarize_status,
    write_report,
)

# These deadlines and recurrence windows are WNBA-owned. They intentionally
# live beside the WNBA monitor rather than in oracle-core.
WNBA_TIME_ZONE = ZoneInfo("America/New_York")
DAILY_DEADLINES_UTC = {
    "dayclose": dt.time(7, 0),
    "job1": dt.time(13, 30),
    "job1late": dt.time(16, 45),
    "job2": dt.time(14, 20),
}
DAILY_WINDOW_STARTS_UTC = {
    "dayclose": dt.time(5, 45),
    "job1": dt.time(12, 45),
    "job1late": dt.time(15, 45),
    "job2": dt.time(13, 45),
}
RECURRING_WINDOWS_UTC = {
    "job1late": (16, 23, dt.timedelta(minutes=50)),
    "job2": (14, 3, dt.timedelta(minutes=20)),
}
HEALTHY_RUN_STATUSES = frozenset({"success", "skipped"})
RUNNING_GRACE = dt.timedelta(minutes=30)
API_CLOCK_SKEW = dt.timedelta(minutes=5)


def _past_deadline(now: dt.datetime, slate_date: dt.date, deadline: dt.time) -> bool:
    """Return whether a deadline has passed in the current WNBA slate day."""

    deadline_at = dt.datetime.combine(slate_date, deadline, tzinfo=dt.UTC)
    return now >= deadline_at


def _in_recurring_window(now: dt.datetime, start_hour: int, end_hour: int) -> bool:
    if start_hour <= end_hour:
        return start_hour <= now.hour <= end_hour
    return now.hour >= start_hour or now.hour <= end_hour


def _not_due_check(job_name: str, deadline: dt.time) -> Check:
    rendered = deadline.isoformat(timespec="minutes")
    return Check(
        f"Scheduled {job_name}",
        "ok",
        f"No run is required before the WNBA-owned {rendered} UTC deadline.",
    )


def _job_run_check(
    job_name: str,
    row: object,
    *,
    now: dt.datetime,
    slate_date: dt.date,
) -> Check:
    deadline = DAILY_DEADLINES_UTC[job_name]
    due = _past_deadline(now, slate_date, deadline)
    if row is None:
        if not due:
            return _not_due_check(job_name, deadline)
        return Check(
            f"Scheduled {job_name}",
            "alert",
            "No durable run was recorded after its WNBA-owned deadline.",
        )
    if not isinstance(row, Mapping):
        return Check(f"Scheduled {job_name}", "alert", "The durable run record is invalid.")

    role = row.get("role")
    if role != job_name:
        return Check(
            f"Scheduled {job_name}",
            "alert",
            "The latest durable run reports the wrong service role.",
        )

    status = str(row.get("status") or "").strip().lower()
    started_at = parse_timestamp(row.get("started_at"))
    completed_at = parse_timestamp(row.get("completed_at"))
    if status == "running":
        if started_at is None:
            return Check(
                f"Scheduled {job_name}",
                "alert",
                "The running heartbeat omitted a valid start time.",
            )
        age = now - started_at
        if age < -API_CLOCK_SKEW or age > RUNNING_GRACE:
            return Check(
                f"Scheduled {job_name}",
                "alert",
                "The latest run heartbeat is stale or has an invalid timestamp.",
            )
        return Check(
            f"Scheduled {job_name}",
            "warn",
            "The latest scheduled run is still in progress within its grace period.",
        )

    exit_code = row.get("exit_code")
    if status not in HEALTHY_RUN_STATUSES or exit_code != 0:
        return Check(
            f"Scheduled {job_name}",
            "alert",
            f"The latest durable run ended with status {status or 'unknown'}.",
        )
    if completed_at is None:
        return Check(
            f"Scheduled {job_name}",
            "alert",
            "The successful durable run omitted a completion time.",
        )
    if started_at is None:
        return Check(
            f"Scheduled {job_name}",
            "alert",
            "The successful durable run omitted a start time.",
        )
    earliest_at = dt.datetime.combine(
        slate_date,
        DAILY_WINDOW_STARTS_UTC[job_name],
        tzinfo=dt.UTC,
    )
    if due and started_at < earliest_at:
        return Check(
            f"Scheduled {job_name}",
            "alert",
            "The latest durable run completed before the expected schedule window.",
        )
    age = now - completed_at
    if age < -API_CLOCK_SKEW:
        return Check(
            f"Scheduled {job_name}",
            "alert",
            "The durable completion timestamp is later than the API clock.",
        )

    recurrence = RECURRING_WINDOWS_UTC.get(job_name)
    if recurrence is not None:
        start_hour, end_hour, max_age = recurrence
        if due and _in_recurring_window(now, start_hour, end_hour) and age > max_age:
            return Check(
                f"Scheduled {job_name}",
                "alert",
                "The latest durable completion is older than its recurrence allowance.",
            )
    return Check(
        f"Scheduled {job_name}",
        "ok",
        "The latest durable run completed successfully within its expected window.",
    )


def job_deadline_checks(payload: object, *, now: dt.datetime) -> list[Check]:
    """Evaluate required WNBA schedules, failing closed only after each deadline."""

    if now.tzinfo is None:
        raise ValueError("now must include a timezone")
    now_utc = now.astimezone(dt.UTC)
    if not isinstance(payload, Mapping):
        return [Check("Scheduled jobs", "alert", "The job heartbeat payload is invalid.")]

    checked_at = parse_timestamp(payload.get("checked_at_utc"))
    if checked_at is None or abs(now_utc - checked_at) > API_CLOCK_SKEW:
        return [
            Check(
                "Scheduled jobs",
                "alert",
                "The job heartbeat payload has a missing or stale API timestamp.",
            )
        ]
    slate_date = payload.get("slate_date")
    try:
        observed_slate_date = dt.date.fromisoformat(str(slate_date))
    except ValueError:
        return [Check("Scheduled jobs", "alert", "The job heartbeat omitted a valid slate date.")]
    expected_slate_date = now_utc.astimezone(WNBA_TIME_ZONE).date()
    if observed_slate_date != expected_slate_date:
        return [
            Check(
                "Scheduled jobs",
                "alert",
                "The job heartbeat reported the wrong WNBA slate date.",
            )
        ]

    jobs = payload.get("jobs")
    if not isinstance(jobs, Mapping):
        return [Check("Scheduled jobs", "alert", "The job heartbeat payload omitted jobs.")]
    return [
        _job_run_check(
            job_name,
            jobs.get(job_name),
            now=now_utc,
            slate_date=observed_slate_date,
        )
        for job_name in DAILY_DEADLINES_UTC
    ]


def _api_check(api_base: str) -> Check:
    try:
        status, health = get_json(f"{api_base}/health")
    except SafeRequestError as exc:
        return Check("API health", "alert", str(exc))
    if status == 200 and isinstance(health, dict) and health.get("status") == "ok":
        return Check("API health", "ok", "The public health endpoint returned OK.")
    return Check("API health", "alert", f"The public health endpoint returned HTTP {status}.")


def _job_checks(api_base: str, *, now: dt.datetime) -> list[Check]:
    try:
        status, payload = get_json(f"{api_base}/watchdog/jobs/today")
    except SafeRequestError as exc:
        return [Check("Scheduled jobs", "alert", str(exc))]
    if status != 200:
        return [Check("Scheduled jobs", "alert", f"The job endpoint returned HTTP {status}.")]
    return job_deadline_checks(payload, now=now)


def _freeze_check(api_base: str) -> Check:
    try:
        status, payload = get_json(f"{api_base}/watchdog/today")
    except SafeRequestError as exc:
        return Check("Frozen lineup watchdog", "alert", str(exc))
    if status != 200 or not isinstance(payload, dict):
        return Check(
            "Frozen lineup watchdog",
            "alert",
            f"The watchdog endpoint returned HTTP {status}.",
        )
    events = payload.get("events")
    if not isinstance(events, list):
        return Check("Frozen lineup watchdog", "alert", "The watchdog payload omitted events.")
    missed = any(
        isinstance(event, dict)
        and event.get("trigger") == "no_frozen_lineup"
        and event.get("severity") == "critical"
        for event in events
    )
    if missed:
        slate_date = str(payload.get("slate_date", "unknown"))
        return Check(
            "Frozen lineup watchdog",
            "alert",
            f"No frozen lineup was present past the deadline for {slate_date}.",
        )
    return Check("Frozen lineup watchdog", "ok", "No overdue frozen lineup alert is active.")


def run(
    api_base: str,
    *,
    heartbeat_url: str = "",
    now: dt.datetime | None = None,
) -> list[Check]:
    base = api_base.rstrip("/")
    observed_at = (now or dt.datetime.now(dt.UTC)).astimezone(dt.UTC)
    checks = [_api_check(base)]
    if checks[0].status != "alert":
        checks.extend(_job_checks(base, now=observed_at))
        checks.append(_freeze_check(base))
    return _heartbeat_checks(checks, heartbeat_url)


def _heartbeat_checks(checks: list[Check], heartbeat_url: str) -> list[Check]:
    """Send a dead-man signal only after every independent check is healthy."""

    if any(check.status != "ok" for check in checks):
        checks.append(
            Check(
                "Monitor heartbeat",
                "warn",
                "Heartbeat was withheld because the independent monitor was not fully healthy.",
            )
        )
        return checks
    if not heartbeat_url.strip():
        checks.append(Check("Monitor heartbeat", "warn", "No heartbeat target is configured."))
        return checks
    try:
        post_heartbeat(heartbeat_url)
    except SafeRequestError as exc:
        checks.append(Check("Monitor heartbeat", "alert", str(exc)))
    else:
        checks.append(Check("Monitor heartbeat", "ok", "Independent heartbeat was accepted."))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default=os.environ.get("WNBA_API_BASE", ""))
    parser.add_argument("--heartbeat-url", default=os.environ.get("WATCHDOG_HEARTBEAT_URL", ""))
    parser.add_argument("--report", required=True)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args()
    if not args.api_base:
        parser.error("--api-base or WNBA_API_BASE is required")

    checks = run(args.api_base, heartbeat_url=args.heartbeat_url)
    write_report(pathlib.Path(args.report), "WNBA Oracle watchdog", checks)
    status = summarize_status(checks)
    append_github_output(args.github_output, status=status, monitor_status=status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
