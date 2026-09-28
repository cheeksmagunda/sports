#!/usr/bin/env python3
"""Scheduled NHL T-40 freeze watchdog.

Uses the public NHL schedule and team-summary feeds. No Real Sports session.
Does not emit a five-player pick. Exits 0; the workflow escalates when
status is ``alert`` or ``error``.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from nhl_oracle.scheduler.watchdog import (
    evaluate_t40_watch,
    render_markdown,
    season_id_for_date,
)

EASTERN = ZoneInfo("America/New_York")
USER_AGENT = "sports-oracle-nhl-t40/1"
SCHEDULE_URL = "https://api-web.nhle.com/v1/schedule/{day}"
SUMMARY_URL = (
    "https://api.nhle.com/stats/rest/en/team/summary"
    "?cayenneExp=seasonId={season}%20and%20gameTypeId=2"
)


def default_target_day(now: datetime | None = None) -> date:
    current = now or datetime.now(UTC)
    return current.astimezone(EASTERN).date()


def _download(url: str, *, timeout: float = 20.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("schedule_payload_not_object")
    return payload


def _load(path: str | None, url: str) -> dict[str, Any]:
    if path:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("json_payload_not_object")
        return payload
    return _download(url)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", help="Slate date YYYY-MM-DD; default today in US/Eastern")
    parser.add_argument("--now", help="Decision clock ISO-8601; default is the current UTC time")
    parser.add_argument("--schedule-json", help="Offline schedule payload")
    parser.add_argument("--summary-json", help="Offline team-summary payload")
    parser.add_argument("--report", help="Optional markdown report path")
    parser.add_argument("--github-output", help="Path to append key=value outputs to")
    args = parser.parse_args(argv)

    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(UTC)
    if now.tzinfo is None:
        print("ERROR: --now must be timezone-aware", file=sys.stderr)
        return 1
    day = date.fromisoformat(args.day) if args.day else default_target_day(now)
    try:
        schedule = _load(args.schedule_json, SCHEDULE_URL.format(day=day.isoformat()))
        summary = _load(
            args.summary_json,
            SUMMARY_URL.format(season=season_id_for_date(day)),
        )
        report = evaluate_t40_watch(day=day, schedule=schedule, team_summary=summary, now=now)
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(f"ERROR: t40_watch_failed:{type(error).__name__}", file=sys.stderr)
        if args.github_output:
            with Path(args.github_output).open("a", encoding="utf-8") as handle:
                handle.write("status=error\n")
                handle.write(f"reason={type(error).__name__}\n")
        return 1

    markdown = render_markdown(report)
    if args.report:
        Path(args.report).write_text(markdown, encoding="utf-8")
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as handle:
            handle.write(f"status={report.status}\n")
            handle.write(f"reason={report.reason}\n")
            handle.write(f"day={report.day.isoformat()}\n")
    print(
        f"status={report.status} reason={report.reason} day={report.day.isoformat()} "
        f"zero_boost_active={str(report.zero_boost_active).lower()} "
        f"freeze_ready={str(report.freeze_ready).lower()}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
