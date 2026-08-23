#!/usr/bin/env python3
"""Validate the WNBA production pipeline before the daily freeze window."""

from __future__ import annotations

import argparse
import os
import pathlib
from collections.abc import Mapping

from ops_common import (
    Check,
    RailwayClient,
    RepairPolicy,
    RunWindow,
    SafeRequestError,
    append_github_output,
    get_json,
    parse_timestamp,
    perform_repair,
    summarize_status,
    write_report,
)

HARD_WATCHDOG_TRIGGERS = {
    "enrichment_from_backfill",
    "job1_pool_degraded",
    "model_artifact_unresolved",
    "model_artifact_unset",
    "no_job1_pool",
    "pool_degenerate_teams",
    "pool_too_small",
}


def _api_is_healthy(api_base: str) -> bool:
    try:
        status, health = get_json(f"{api_base}/health")
    except SafeRequestError:
        return False
    return status == 200 and isinstance(health, dict) and health.get("status") == "ok"


def _job1_durable_run_check(payload: object, *, window: RunWindow) -> Check:
    """Validate Job 1 from the durable application-owned run ledger."""

    if not isinstance(payload, Mapping):
        return Check("Job 1 run", "alert", "The durable job-run payload is invalid.")
    if str(payload.get("slate_date") or "") != window.slate_date:
        return Check(
            "Job 1 run", "alert", "The durable job-run payload reported the wrong slate date."
        )
    jobs = payload.get("jobs")
    if not isinstance(jobs, Mapping):
        return Check("Job 1 run", "alert", "The durable job-run payload omitted jobs.")
    row = jobs.get(window.role)
    if not isinstance(row, Mapping):
        return Check(
            "Job 1 run", "alert", "No durable Job 1 run was recorded in the requested window."
        )
    if row.get("role") != window.role:
        return Check("Job 1 run", "alert", "The durable run reports the wrong service role.")
    if str(row.get("status") or "").lower() != "success" or row.get("exit_code") != 0:
        return Check("Job 1 run", "alert", "The durable Job 1 run did not complete successfully.")
    started_at = parse_timestamp(row.get("started_at"))
    completed_at = parse_timestamp(row.get("completed_at"))
    if started_at is None or completed_at is None:
        return Check("Job 1 run", "alert", "The durable Job 1 run omitted valid timestamps.")
    if not window.contains(started_at) or not window.contains(completed_at):
        return Check(
            "Job 1 run", "alert", "The durable Job 1 run fell outside the requested window."
        )
    return Check(
        "Job 1 run", "ok", "The durable Job 1 run completed successfully in the requested window."
    )


def _api_checks(
    api_base: str,
    slate_date: str,
    *,
    window: RunWindow,
) -> tuple[list[Check], bool]:
    checks: list[Check] = []
    health_failed = False
    try:
        status, health = get_json(f"{api_base}/health")
        if status == 200 and isinstance(health, dict) and health.get("status") == "ok":
            checks.append(Check("API health", "ok", "The public API returned OK."))
        else:
            health_failed = True
            checks.append(
                Check("API health", "alert", f"The health endpoint returned HTTP {status}.")
            )
    except SafeRequestError as exc:
        health_failed = True
        checks.append(Check("API health", "alert", str(exc)))

    try:
        status, payload = get_json(f"{api_base}/watchdog/{slate_date}?severity_min=warn")
        if status != 200 or not isinstance(payload, dict):
            checks.append(
                Check("Pipeline watchdog", "alert", f"The endpoint returned HTTP {status}.")
            )
        else:
            events = payload.get("events")
            event_list = events if isinstance(events, list) else []
            triggers = sorted(
                {
                    str(event.get("trigger"))
                    for event in event_list
                    if isinstance(event, dict) and event.get("trigger")
                }
            )
            hard = sorted(HARD_WATCHDOG_TRIGGERS.intersection(triggers))
            if hard:
                checks.append(
                    Check("Pipeline watchdog", "alert", f"Active triggers: {', '.join(hard)}.")
                )
            elif triggers:
                checks.append(
                    Check("Pipeline watchdog", "warn", f"Advisory triggers: {', '.join(triggers)}.")
                )
            else:
                checks.append(Check("Pipeline watchdog", "ok", "No pipeline events are active."))
    except SafeRequestError as exc:
        checks.append(Check("Pipeline watchdog", "alert", str(exc)))

    try:
        status, job_runs = get_json(f"{api_base}/watchdog/jobs/today")
        if status != 200:
            checks.append(
                Check("Job 1 run", "alert", f"The durable job endpoint returned HTTP {status}.")
            )
        else:
            checks.append(_job1_durable_run_check(job_runs, window=window))
    except SafeRequestError as exc:
        checks.append(Check("Job 1 run", "alert", str(exc)))

    try:
        status, slate = get_json(f"{api_base}/slate/{slate_date}")
        if status == 200 and isinstance(slate, dict):
            target = str(slate.get("freeze_target_utc") or "not set")
            paused = bool(slate.get("picks_paused"))
            summary = "Picks are intentionally paused." if paused else f"Freeze target: {target}."
            checks.append(Check("Slate timing", "ok", summary))
        elif status == 404:
            checks.append(Check("Slate timing", "ok", "No slate timing was captured for today."))
        else:
            checks.append(Check("Slate timing", "warn", f"The endpoint returned HTTP {status}."))
    except SafeRequestError as exc:
        checks.append(Check("Slate timing", "warn", str(exc)))
    return checks, health_failed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default=os.environ.get("WNBA_API_BASE", ""))
    parser.add_argument("--project-id", default=os.environ.get("WNBA_RAILWAY_PROJECT_ID", ""))
    parser.add_argument(
        "--environment-id", default=os.environ.get("WNBA_RAILWAY_ENVIRONMENT_ID", "")
    )
    parser.add_argument(
        "--api-service-id", default=os.environ.get("WNBA_RAILWAY_API_SERVICE_ID", "")
    )
    parser.add_argument("--slate-date", required=True)
    parser.add_argument("--run-start-utc", required=True)
    parser.add_argument("--run-end-utc", required=True)
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--repair-attempts", type=int, default=2)
    parser.add_argument("--repair-cooldown-seconds", type=float, default=60.0)
    parser.add_argument("--repair-postcheck-seconds", type=float, default=20.0)
    parser.add_argument("--report", required=True)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args()

    required = {"api-base": args.api_base}
    if args.repair:
        required.update(
            {
                "project-id": args.project_id,
                "environment-id": args.environment_id,
                "api-service-id": args.api_service_id,
            }
        )
    missing = [name for name, value in required.items() if not value]
    if missing:
        parser.error(f"missing required configuration: {', '.join(missing)}")

    try:
        window = RunWindow.from_strings(
            role="job1",
            slate_date=args.slate_date,
            started_at=args.run_start_utc,
            ended_at=args.run_end_utc,
        )
        repair_policy = RepairPolicy(
            attempts=args.repair_attempts,
            cooldown_seconds=args.repair_cooldown_seconds,
            postcheck_seconds=args.repair_postcheck_seconds,
        )
    except ValueError as exc:
        parser.error(str(exc))

    api_base = args.api_base.rstrip("/")
    checks, health_failed = _api_checks(api_base, args.slate_date, window=window)
    if args.repair:
        token = os.environ.get("RAILWAY_WORKSPACE_TOKEN", "")
        if not token:
            checks.append(
                Check(
                    "Allowlisted repair",
                    "alert",
                    "RAILWAY_WORKSPACE_TOKEN is missing for the requested repair.",
                )
            )
        else:
            railway = RailwayClient(token)
            if not health_failed:
                checks.append(
                    Check(
                        "Allowlisted repair",
                        "ok",
                        "No repair was needed because API health passed.",
                    )
                )
            else:
                result = perform_repair(
                    lambda: railway.deploy_service(args.api_service_id, args.environment_id),
                    lambda: _api_is_healthy(api_base),
                    policy=repair_policy,
                )
                if result.recovered:
                    checks.append(
                        Check(
                            "Allowlisted repair",
                            "warn",
                            f"API health recovered after {result.attempts} bounded redeploy attempt(s).",
                        )
                    )
                else:
                    checks.append(
                        Check(
                            "Allowlisted repair",
                            "alert",
                            f"API health did not recover after {result.attempts} bounded redeploy attempt(s).",
                        )
                    )

    report = pathlib.Path(args.report)
    write_report(
        report,
        f"WNBA pre-freeze guard for {args.slate_date}",
        checks,
        notes=[
            f"Durable Job 1 evidence was limited to {window.describe()}.",
            "The scheduled path uses public API and durable application evidence only.",
            "Repair is manual, limited to API redeploys, and requires a health postcheck.",
            "Real Sports session recovery always requires the documented operator flow.",
        ],
    )
    status = summarize_status(checks)
    append_github_output(args.github_output, status=status)
    return 1 if status == "alert" else 0


if __name__ == "__main__":
    raise SystemExit(main())
