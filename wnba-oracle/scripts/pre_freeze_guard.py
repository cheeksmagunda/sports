#!/usr/bin/env python3
"""Validate the WNBA production pipeline before the daily freeze window."""

from __future__ import annotations

import argparse
import os
import pathlib

from ops_common import (
    Check,
    RailwayClient,
    RepairPolicy,
    RunWindow,
    SafeRequestError,
    append_github_output,
    contains_any,
    get_json,
    log_messages,
    perform_repair,
    run_evidence_checks,
    safe_sha,
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
AUTH_FAILURE_MARKERS = (
    "auth_required_stats",
    "auth_required_entries",
    "platformauthrequired",
    "storage state not found",
    "session has expired",
    "did not capture authenticated headers",
    "401 on",
)


def _api_is_healthy(api_base: str) -> bool:
    try:
        status, health = get_json(f"{api_base}/health")
    except SafeRequestError:
        return False
    return status == 200 and isinstance(health, dict) and health.get("status") == "ok"


def _api_checks(api_base: str, slate_date: str) -> tuple[list[Check], bool]:
    checks: list[Check] = []
    health_failed = False
    try:
        status, health = get_json(f"{api_base}/health")
        if status == 200 and isinstance(health, dict) and health.get("status") == "ok":
            checks.append(Check("API health", "ok", "The public API returned OK."))
        else:
            health_failed = True
            checks.append(Check("API health", "alert", f"The health endpoint returned HTTP {status}."))
    except SafeRequestError as exc:
        health_failed = True
        checks.append(Check("API health", "alert", str(exc)))

    try:
        status, payload = get_json(f"{api_base}/watchdog/{slate_date}?severity_min=warn")
        if status != 200 or not isinstance(payload, dict):
            checks.append(Check("Pipeline watchdog", "alert", f"The endpoint returned HTTP {status}."))
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
                checks.append(Check("Pipeline watchdog", "alert", f"Active triggers: {', '.join(hard)}."))
            elif triggers:
                checks.append(Check("Pipeline watchdog", "warn", f"Advisory triggers: {', '.join(triggers)}."))
            else:
                checks.append(Check("Pipeline watchdog", "ok", "No pipeline events are active."))
    except SafeRequestError as exc:
        checks.append(Check("Pipeline watchdog", "alert", str(exc)))

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


def _railway_checks(
    railway: RailwayClient,
    *,
    project_id: str,
    environment_id: str,
    job1_service_id: str,
    job1_late_service_id: str,
    job2_service_id: str,
    expected_model_sha: str,
    window: RunWindow,
) -> list[Check]:
    checks: list[Check] = []
    try:
        deployments, logs = railway.evidence_for_window(project_id, job1_service_id, window)
    except SafeRequestError as exc:
        checks.append(Check("Job 1 Railway check", "alert", str(exc)))
    else:
        checks.extend(
            run_evidence_checks(
                deployment_name="Job 1 deployment",
                completion_name="Job 1 run",
                completion_event="job1_done",
                deployments=deployments,
                logs=logs,
                window=window,
            )
        )
        messages = log_messages(logs)
        if contains_any(messages, AUTH_FAILURE_MARKERS):
            checks.append(Check("Real Sports session", "alert", "Job 1 logs contain an authentication failure."))
        elif contains_any(messages, ("job1_failed", "job1_pool_degraded")):
            checks.append(Check("Job 1 outcome", "alert", "Job 1 logs contain a failed or degraded run."))
        else:
            checks.append(
                Check(
                    "Job 1 outcome",
                    "ok",
                    "No authentication or degraded-run signature was found in the declared run window.",
                )
            )

    service_ids = {
        "job1": job1_service_id,
        "job1-late": job1_late_service_id,
        "job2": job2_service_id,
    }
    configured: dict[str, str] = {}
    try:
        for name, service_id in service_ids.items():
            values = railway.variables(project_id, environment_id, service_id)
            configured[name] = values.get("WNBA_ORACLE_MODEL_ARTIFACT_SHA", "").strip().lower()
        present = {value for value in configured.values() if value}
        missing = sorted(name for name, value in configured.items() if not value)
        if missing:
            checks.append(Check("Model configuration", "alert", f"Model SHA is unset on: {', '.join(missing)}."))
        elif len(present) != 1:
            shown = ", ".join(f"{name}={safe_sha(value)}" for name, value in configured.items())
            checks.append(Check("Model configuration", "alert", f"Service SHAs differ: {shown}."))
        elif expected_model_sha and present != {expected_model_sha.lower()}:
            actual = safe_sha(next(iter(present)))
            checks.append(
                Check(
                    "Model configuration",
                    "alert",
                    f"Configured SHA {actual} differs from expected {safe_sha(expected_model_sha)}.",
                )
            )
        else:
            checks.append(
                Check(
                    "Model configuration",
                    "ok",
                    f"All prediction services use SHA {safe_sha(next(iter(present)))}.",
                )
            )
    except SafeRequestError as exc:
        checks.append(Check("Model configuration", "alert", str(exc)))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default=os.environ.get("WNBA_API_BASE", ""))
    parser.add_argument("--project-id", default=os.environ.get("WNBA_RAILWAY_PROJECT_ID", ""))
    parser.add_argument("--environment-id", default=os.environ.get("WNBA_RAILWAY_ENVIRONMENT_ID", ""))
    parser.add_argument("--api-service-id", default=os.environ.get("WNBA_RAILWAY_API_SERVICE_ID", ""))
    parser.add_argument("--job1-service-id", default=os.environ.get("WNBA_RAILWAY_JOB1_SERVICE_ID", ""))
    parser.add_argument(
        "--job1-late-service-id", default=os.environ.get("WNBA_RAILWAY_JOB1_LATE_SERVICE_ID", "")
    )
    parser.add_argument("--job2-service-id", default=os.environ.get("WNBA_RAILWAY_JOB2_SERVICE_ID", ""))
    parser.add_argument("--expected-model-sha", default=os.environ.get("WNBA_EXPECTED_MODEL_SHA", ""))
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

    required = {
        "api-base": args.api_base,
        "project-id": args.project_id,
        "environment-id": args.environment_id,
        "api-service-id": args.api_service_id,
        "job1-service-id": args.job1_service_id,
        "job1-late-service-id": args.job1_late_service_id,
        "job2-service-id": args.job2_service_id,
        "expected-model-sha": args.expected_model_sha,
    }
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
    checks, health_failed = _api_checks(api_base, args.slate_date)
    token = os.environ.get("RAILWAY_WORKSPACE_TOKEN", "")
    if token:
        railway = RailwayClient(token)
        checks.extend(
            _railway_checks(
                railway,
                project_id=args.project_id,
                environment_id=args.environment_id,
                job1_service_id=args.job1_service_id,
                job1_late_service_id=args.job1_late_service_id,
                job2_service_id=args.job2_service_id,
                expected_model_sha=args.expected_model_sha,
                window=window,
            )
        )
        if args.repair:
            if not health_failed:
                checks.append(Check("Allowlisted repair", "ok", "No repair was needed because API health passed."))
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
    else:
        checks.append(Check("Railway credential", "alert", "RAILWAY_WORKSPACE_TOKEN is missing."))

    report = pathlib.Path(args.report)
    write_report(
        report,
        f"WNBA pre-freeze guard for {args.slate_date}",
        checks,
        notes=[
            f"Railway evidence was limited to {window.describe()}.",
            "Repair is manual, limited to API redeploys, and requires a health postcheck.",
            "Real Sports session recovery always requires the documented operator flow.",
        ],
    )
    append_github_output(args.github_output, status=summarize_status(checks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
