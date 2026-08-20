#!/usr/bin/env python3
"""Verify the WNBA day-close cron using public HTTP and Railway GraphQL."""

from __future__ import annotations

import argparse
import os
import pathlib

from ops_common import (
    Check,
    RailwayClient,
    RunWindow,
    SafeRequestError,
    append_github_output,
    contains_any,
    get_json,
    log_messages,
    run_evidence_checks,
    safe_sha,
    structured_events,
    summarize_status,
    write_report,
)

AUTH_FAILURE_MARKERS = (
    "auth_required_stats",
    "auth_required_entries",
    "platformauthrequired",
    "storage state not found",
    "session has expired",
    "did not capture authenticated headers",
    "401 on",
)


def _public_api_checks(api_base: str, slate_date: str) -> list[Check]:
    checks: list[Check] = []
    try:
        status, health = get_json(f"{api_base}/health")
        if status == 200 and isinstance(health, dict) and health.get("status") == "ok":
            checks.append(Check("API health", "ok", "The public API returned OK."))
        else:
            checks.append(Check("API health", "alert", f"The health endpoint returned HTTP {status}."))
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
            checks.append(Check("Served lineup", "ok", "No frozen lineup was served for this date."))
        else:
            checks.append(Check("Served lineup", "warn", f"The endpoint returned HTTP {status}."))
    except SafeRequestError as exc:
        checks.append(Check("Served lineup", "warn", str(exc)))

    try:
        status, payload = get_json(f"{api_base}/watchdog/{slate_date}?severity_min=warn")
        if status != 200 or not isinstance(payload, dict):
            checks.append(Check("Day-close watchdog", "alert", f"The endpoint returned HTTP {status}."))
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
                checks.append(Check("Day-close watchdog", "alert", f"Triggers: {', '.join(triggers)}."))
            elif triggers:
                checks.append(Check("Day-close watchdog", "warn", f"Advisories: {', '.join(triggers)}."))
            else:
                checks.append(Check("Day-close watchdog", "ok", "No watchdog events were recorded."))
    except SafeRequestError as exc:
        checks.append(Check("Day-close watchdog", "alert", str(exc)))
    return checks


def _railway_checks(
    railway: RailwayClient, project_id: str, service_id: str, window: RunWindow
) -> list[Check]:
    checks: list[Check] = []
    try:
        deployments, logs = railway.evidence_for_window(project_id, service_id, window)
    except SafeRequestError as exc:
        return [Check("Day-close Railway check", "alert", str(exc))]

    checks.extend(
        run_evidence_checks(
            deployment_name="Day-close deployment",
            completion_name="Day-close",
            completion_event="historical_backfill_done",
            deployments=deployments,
            logs=logs,
            window=window,
            require_slate_event=False,
        )
    )

    messages = log_messages(logs)
    if contains_any(messages, AUTH_FAILURE_MARKERS):
        checks.append(
            Check(
                "Real Sports session",
                "alert",
                "Day-close logs contain the session-expiry or HTTP 401 signature.",
            )
        )
    else:
        checks.append(Check("Real Sports session", "ok", "No authentication failure signature was found."))

    completed = structured_events(logs, "historical_backfill_done", window=window)
    if completed:
        latest = completed[-1]
        n_success = int(latest.get("n_success") or 0)
        n_auth_failed = int(latest.get("n_auth_failed") or 0)
        n_entries = int(latest.get("n_lb_entries") or 0)
        level = "alert" if n_auth_failed else "ok"
        checks.append(
            Check(
                "Corpus walk",
                level,
                f"Completed with {n_success} contests, {n_entries} leaderboard rows, and {n_auth_failed} auth failures.",
            )
        )
    else:
        checks.append(
            Check(
                "Corpus walk",
                "alert",
                "No historical_backfill_done event was visible in the declared run window.",
            )
        )

    if contains_any(messages, ("dayclose_game_logs_refreshed",)):
        checks.append(Check("Game-log refresh", "ok", "The refresh completion event was present."))
    elif contains_any(messages, ("dayclose_game_logs_refresh_failed",)):
        checks.append(Check("Game-log refresh", "warn", "The best-effort refresh reported a failure."))
    else:
        checks.append(Check("Game-log refresh", "warn", "No refresh event was visible in recent logs."))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default=os.environ.get("WNBA_API_BASE", ""))
    parser.add_argument("--project-id", default=os.environ.get("WNBA_RAILWAY_PROJECT_ID", ""))
    parser.add_argument(
        "--dayclose-service-id", default=os.environ.get("WNBA_RAILWAY_DAYCLOSE_SERVICE_ID", "")
    )
    parser.add_argument("--slate-date", required=True)
    parser.add_argument("--run-start-utc", required=True)
    parser.add_argument("--run-end-utc", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args()
    if not args.api_base or not args.project_id or not args.dayclose_service_id:
        parser.error("API base, Railway project ID, and day-close service ID are required")

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
    token = os.environ.get("RAILWAY_WORKSPACE_TOKEN", "")
    if token:
        checks.extend(
            _railway_checks(RailwayClient(token), args.project_id, args.dayclose_service_id, window)
        )
    else:
        checks.append(Check("Railway credential", "alert", "RAILWAY_WORKSPACE_TOKEN is missing."))

    write_report(
        pathlib.Path(args.report),
        f"WNBA day-close verification for {args.slate_date}",
        checks,
        notes=[
            f"Railway evidence was limited to {window.describe()}.",
            "Contest labels can arrive several days late because the bounded walk intentionally overlaps.",
            "Real Sports session recovery is operator-only and is never attempted by this workflow.",
        ],
    )
    append_github_output(args.github_output, status=summarize_status(checks), slate_date=args.slate_date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
