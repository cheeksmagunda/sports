#!/usr/bin/env python3
"""Verify the WNBA day-close cron using public durable application evidence."""

from __future__ import annotations

import argparse
import os
import pathlib

from ops_common import (
    Check,
    RunWindow,
    SafeRequestError,
    append_github_output,
    get_json,
    parse_timestamp,
    safe_sha,
    summarize_status,
    write_report,
)

REQUIRED_DAYCLOSE_SUBSTEPS = frozenset(
    {
        "contest_discovery",
        "historical_backfill",
        "label_coverage",
        "placement_capture",
        "game_log_refresh",
    }
)


def _public_api_checks(api_base: str, slate_date: str) -> list[Check]:
    checks: list[Check] = []
    try:
        status, health = get_json(f"{api_base}/health")
        if status == 200 and isinstance(health, dict) and health.get("status") == "ok":
            checks.append(Check("API health", "ok", "The public API returned OK."))
        else:
            checks.append(
                Check("API health", "alert", f"The health endpoint returned HTTP {status}.")
            )
    except SafeRequestError as exc:
        checks.append(Check("API health", "alert", str(exc)))

    try:
        status, lineup = get_json(f"{api_base}/lineup/{slate_date}")
        if status == 200 and isinstance(lineup, dict):
            model_sha = safe_sha(str(lineup.get("model_sha", "")))
            freeze_seq = lineup.get("freeze_seq", "unknown")
            payout = lineup.get("expected_payout")
            checks.append(
                Check(
                    "Served lineup",
                    "ok",
                    f"Freeze {freeze_seq}, model {model_sha}, expected payout {payout}.",
                )
            )
        elif status == 404:
            checks.append(
                Check("Served lineup", "ok", "No frozen lineup was served for this date.")
            )
        else:
            checks.append(Check("Served lineup", "warn", f"The endpoint returned HTTP {status}."))
    except SafeRequestError as exc:
        checks.append(Check("Served lineup", "warn", str(exc)))

    try:
        status, payload = get_json(f"{api_base}/watchdog/{slate_date}?severity_min=warn")
        if status != 200 or not isinstance(payload, dict):
            checks.append(
                Check("Day-close watchdog", "alert", f"The endpoint returned HTTP {status}.")
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
            critical = any(
                isinstance(event, dict) and event.get("severity") in {"error", "critical"}
                for event in event_list
            )
            if critical:
                checks.append(
                    Check("Day-close watchdog", "alert", f"Triggers: {', '.join(triggers)}.")
                )
            elif triggers:
                checks.append(
                    Check("Day-close watchdog", "warn", f"Advisories: {', '.join(triggers)}.")
                )
            else:
                checks.append(
                    Check("Day-close watchdog", "ok", "No watchdog events were recorded.")
                )
    except SafeRequestError as exc:
        checks.append(Check("Day-close watchdog", "alert", str(exc)))
    return checks


def _durable_dayclose_checks(api_base: str, window: RunWindow) -> list[Check]:
    try:
        status, payload = get_json(f"{api_base}/watchdog/jobs/today")
    except SafeRequestError as exc:
        return [Check("Durable day-close", "alert", str(exc))]
    if status != 200 or not isinstance(payload, dict):
        return [Check("Durable day-close", "alert", f"The job endpoint returned HTTP {status}.")]
    jobs = payload.get("jobs")
    row = jobs.get("dayclose") if isinstance(jobs, dict) else None
    if not isinstance(row, dict) or row.get("role") != "dayclose":
        return [Check("Durable day-close", "alert", "No valid day-close record was returned.")]

    started_at = parse_timestamp(row.get("started_at"))
    completed_at = parse_timestamp(row.get("completed_at"))
    if not window.contains(started_at) or not window.contains(completed_at):
        return [
            Check(
                "Durable day-close",
                "alert",
                "The latest completion falls outside the declared run window.",
            )
        ]

    job_status = str(row.get("status") or "").lower()
    exit_code = row.get("exit_code")
    if job_status not in {"success", "degraded"}:
        return [
            Check(
                "Durable day-close",
                "alert",
                f"The durable run ended with status {job_status or 'unknown'}.",
            )
        ]
    expected_exit_code = 0 if job_status == "success" else 2
    if exit_code != expected_exit_code:
        return [
            Check(
                "Durable day-close",
                "alert",
                "The durable status and process exit code disagree.",
            )
        ]

    details = row.get("details")
    processed_slate_date = (
        details.get("processed_slate_date") if isinstance(details, dict) else None
    )
    if processed_slate_date != window.slate_date:
        return [
            Check(
                "Durable day-close",
                "alert",
                "The durable run did not prove the requested processed slate.",
            )
        ]
    substeps = details.get("substeps") if isinstance(details, dict) else None
    if not isinstance(substeps, dict):
        return [Check("Durable day-close", "alert", "Substep outcomes were not recorded.")]
    missing = sorted(REQUIRED_DAYCLOSE_SUBSTEPS - set(substeps))
    allowed_statuses = {
        name: ({"success", "skipped"} if name == "game_log_refresh" else {"success", "degraded"})
        for name in REQUIRED_DAYCLOSE_SUBSTEPS
    }
    invalid = sorted(
        name
        for name in REQUIRED_DAYCLOSE_SUBSTEPS
        if not isinstance(substeps.get(name), dict)
        or substeps[name].get("status") not in allowed_statuses[name]
    )
    if missing or invalid:
        summary_parts = []
        if missing:
            summary_parts.append(f"missing: {', '.join(missing)}")
        if invalid:
            summary_parts.append(f"failed: {', '.join(invalid)}")
        return [
            Check(
                "Durable day-close",
                "alert",
                "Required substep evidence is incomplete (" + "; ".join(summary_parts) + ").",
            )
        ]

    required_failures = details.get("required_failures") if isinstance(details, dict) else None
    degraded = details.get("degraded_substeps") if isinstance(details, dict) else None
    required_degraded = any(
        substeps[name].get("status") == "degraded" for name in REQUIRED_DAYCLOSE_SUBSTEPS
    )
    if required_failures or (job_status == "success" and required_degraded):
        return [
            Check(
                "Durable day-close",
                "alert",
                "The overall result conflicts with its required substep outcomes.",
            )
        ]

    if job_status == "degraded":
        if not isinstance(degraded, list) or not degraded:
            return [
                Check(
                    "Durable day-close",
                    "alert",
                    "The degraded result omitted its degraded substep list.",
                )
            ]
        names = ", ".join(degraded)
        return [
            Check(
                "Durable day-close",
                "warn",
                f"Required work completed with degraded substeps: {names}.",
            )
        ]
    return [
        Check(
            "Durable day-close",
            "ok",
            "Required durable substeps completed successfully in the declared window.",
        )
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default=os.environ.get("WNBA_API_BASE", ""))
    parser.add_argument("--slate-date", required=True)
    parser.add_argument("--run-start-utc", required=True)
    parser.add_argument("--run-end-utc", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args()
    if not args.api_base:
        parser.error("API base is required")

    try:
        window = RunWindow.from_strings(
            role="dayclose",
            slate_date=args.slate_date,
            started_at=args.run_start_utc,
            ended_at=args.run_end_utc,
        )
    except ValueError as exc:
        parser.error(str(exc))

    checks = _public_api_checks(args.api_base.rstrip("/"), args.slate_date)
    checks.extend(_durable_dayclose_checks(args.api_base.rstrip("/"), window))

    write_report(
        pathlib.Path(args.report),
        f"WNBA day-close verification for {args.slate_date}",
        checks,
        notes=[
            f"Durable application evidence was limited to {window.describe()}.",
            "Contest labels can arrive several days late because the bounded walk intentionally overlaps.",
            "Real Sports session recovery is operator-only and is never attempted by this workflow.",
        ],
    )
    status = summarize_status(checks)
    append_github_output(args.github_output, status=status, slate_date=args.slate_date)
    return 1 if status == "alert" else 0


if __name__ == "__main__":
    raise SystemExit(main())
