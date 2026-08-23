#!/usr/bin/env python3
"""Verify one new successful durable job outcome through the public API."""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Mapping
from typing import Literal

from ops_common import SafeRequestError, get_json, parse_timestamp


def classify_outcome(
    payload: object,
    *,
    role: str,
    started_after: str,
) -> Literal["success", "failed", "pending"]:
    threshold = parse_timestamp(started_after)
    if threshold is None or not isinstance(payload, Mapping):
        return "pending"
    jobs = payload.get("jobs")
    if not isinstance(jobs, Mapping):
        return "pending"
    row = jobs.get(role)
    if not isinstance(row, Mapping) or row.get("role") != role:
        return "pending"
    started_at = parse_timestamp(row.get("started_at"))
    completed_at = parse_timestamp(row.get("completed_at"))
    if started_at is None or started_at < threshold:
        return "pending"
    if completed_at is None:
        return "pending"
    if completed_at < started_at:
        return "failed"
    if str(row.get("status") or "").lower() == "success" and row.get("exit_code") == 0:
        return "success"
    return "failed"


def wait_for_outcome(
    api_base: str,
    *,
    role: str,
    started_after: str,
    timeout_seconds: float,
    interval_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> Literal["success", "failed", "timeout"]:
    deadline = monotonic() + timeout_seconds
    endpoint = f"{api_base.rstrip('/')}/watchdog/jobs/today"
    while True:
        try:
            status, payload = get_json(endpoint)
        except SafeRequestError:
            status, payload = 0, None
        if status == 200:
            outcome = classify_outcome(
                payload,
                role=role,
                started_after=started_after,
            )
            if outcome != "pending":
                return outcome
        remaining = deadline - monotonic()
        if remaining <= 0:
            return "timeout"
        sleep(min(interval_seconds, remaining))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--started-after", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    args = parser.parse_args()
    if not 1 <= args.timeout_seconds <= 600:
        parser.error("timeout must be between 1 and 600 seconds")
    if not 0.5 <= args.interval_seconds <= 30:
        parser.error("interval must be between 0.5 and 30 seconds")
    if parse_timestamp(args.started_after) is None:
        parser.error("started-after must be an ISO-8601 timestamp with a timezone")

    outcome = wait_for_outcome(
        args.api_base,
        role=args.role,
        started_after=args.started_after,
        timeout_seconds=args.timeout_seconds,
        interval_seconds=args.interval_seconds,
    )
    if outcome == "success":
        print(f"durable {args.role} outcome verified")
        return 0
    if outcome == "failed":
        print(f"durable {args.role} outcome reported failure")
        return 1
    print(f"durable {args.role} outcome was not verified before timeout")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
