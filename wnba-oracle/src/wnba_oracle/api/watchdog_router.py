"""Operator-facing watchdog surface.

Returns the most recent watchdog events for a slate date so the
operator can curl from a phone without Railway log access. Frontend
can also surface a small banner when there's a critical event for
today's slate.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from wnba_oracle.common.clock import slate_date as current_slate_date
from wnba_oracle.db.engine import get_api_engine as get_engine
from wnba_oracle.scheduler.job_runtime import JOB_NAMES

router = APIRouter(prefix="/watchdog", tags=["watchdog"])


@router.get("/today")
def get_watchdog_today(
    severity_min: str = Query(default="warn", pattern="^(warn|error|critical)$"),
) -> dict[str, Any]:
    """Convenience: same as /watchdog/{slate_date} for today's UTC date.

    Useful for a curl-from-phone health check:
        curl https://<api-domain>/watchdog/today | jq .status

    Declared BEFORE the ``/{slate_date}`` route so FastAPI matches the
    specific path first — otherwise a request to ``/watchdog/today``
    silently binds ``slate_date="today"`` and returns an empty event
    list against the bogus slate.
    """
    today = current_slate_date().isoformat()
    return get_watchdog_for_slate(today, severity_min=severity_min)


@router.get("/jobs/today")
def get_job_runs_today() -> dict[str, Any]:
    """Return durable latest-run facts for independent schedule monitoring."""

    today = current_slate_date().isoformat()
    try:
        engine = get_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    query = text(
        "SELECT DISTINCT ON (job_name) job_name, role, status, started_at, "
        "completed_at, exit_code, details_json FROM job_runs WHERE slate_date = :slate_date "
        "ORDER BY job_name, started_at DESC"
    )
    with engine.connect() as connection:
        rows = list(connection.execute(query, {"slate_date": today}))

    latest: dict[str, Any] = dict.fromkeys(JOB_NAMES)
    for row in rows:
        values = row._mapping
        latest[str(values["job_name"])] = {
            "role": values["role"],
            "status": values["status"],
            "started_at": _isoformat(values.get("started_at")),
            "completed_at": _isoformat(values.get("completed_at")),
            "exit_code": values.get("exit_code"),
            "details": _public_job_details(str(values["job_name"]), values.get("details_json")),
        }
    return {
        "slate_date": today,
        "checked_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "jobs": latest,
    }


@router.get("/{slate_date}")
def get_watchdog_for_slate(
    slate_date: str,
    severity_min: str = Query(
        default="warn",
        pattern="^(warn|error|critical)$",
        description="Minimum severity to surface (warn|error|critical).",
    ),
) -> dict[str, Any]:
    """Return all watchdog events for the slate at or above the
    requested minimum severity, ordered most-recent-first.

    Severity ordering: warn < error < critical. ``severity_min=warn``
    returns everything; ``severity_min=critical`` returns only the
    flag-this-fast events.
    """
    severity_rank = {"warn": 0, "error": 1, "critical": 2}
    min_rank = severity_rank[severity_min]

    try:
        eng = get_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    q = text(
        "SELECT trigger, severity, payload_json, created_at "
        "FROM watchdog_events WHERE slate_date = :sd "
        "ORDER BY created_at DESC LIMIT 50"
    )
    with eng.connect() as conn:
        rows = list(conn.execute(q, {"sd": slate_date}))

    events = []
    for r in rows:
        m = r._mapping
        if severity_rank.get(m["severity"], 0) < min_rank:
            continue
        events.append(
            {
                "trigger": m["trigger"],
                "severity": m["severity"],
                "payload": m["payload_json"],
                "created_at": m["created_at"].isoformat() if m.get("created_at") else None,
            }
        )

    return {
        "slate_date": slate_date,
        "checked_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "events": events,
        "status": _summarize(events),
    }


def _summarize(events: list[dict]) -> str:
    """Compact ``status`` string the operator can grep at a glance."""
    if not events:
        return "ok"
    severities = {e["severity"] for e in events}
    if "critical" in severities:
        return "critical"
    if "error" in severities:
        return "error"
    return "warn"


def _isoformat(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _public_job_details(job_name: str, value: object) -> dict[str, Any]:
    """Project durable details onto a value-free, explicitly allowed shape."""

    if not isinstance(value, Mapping):
        return {}
    public: dict[str, Any] = {}
    source_exit_code = value.get("source_exit_code")
    if isinstance(source_exit_code, int):
        public["source_exit_code"] = source_exit_code
    if job_name != "dayclose":
        return public

    processed_slate_date = value.get("processed_slate_date")
    if isinstance(processed_slate_date, str):
        try:
            public["processed_slate_date"] = dt.date.fromisoformat(processed_slate_date).isoformat()
        except ValueError:
            pass

    for key in ("required_failures", "degraded_substeps"):
        raw = value.get(key)
        if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
            public[key] = list(raw)
    raw_substeps = value.get("substeps")
    if isinstance(raw_substeps, Mapping):
        substeps: dict[str, dict[str, str]] = {}
        for name, outcome in raw_substeps.items():
            if not isinstance(name, str) or not isinstance(outcome, Mapping):
                continue
            status = outcome.get("status")
            if status in {"success", "degraded", "failed", "skipped"}:
                substeps[name] = {"status": str(status)}
        public["substeps"] = substeps
    return public
