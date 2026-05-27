"""Operator-facing watchdog surface.

Returns the most recent watchdog events for a slate date so the
operator can curl from a phone without Railway log access. Frontend
can also surface a small banner when there's a critical event for
today's slate.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from wnba_oracle.db.engine import get_engine

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
    today = dt.datetime.now(dt.UTC).date().isoformat()
    return get_watchdog_for_slate(today, severity_min=severity_min)


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
