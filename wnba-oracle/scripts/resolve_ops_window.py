#!/usr/bin/env python3
"""Resolve validated manual or scheduled WNBA operations run windows."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
from collections.abc import Mapping
from zoneinfo import ZoneInfo

from ops_common import RunWindow, parse_timestamp

WNBA_TIME_ZONE = ZoneInfo("America/New_York")
SCHEDULE_WINDOWS_UTC = {
    "job1": (dt.time(12, 45), dt.time(13, 30)),
    "dayclose": (dt.time(5, 45), dt.time(7, 0)),
}


def _iso_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def scheduled_window(role: str, *, now: dt.datetime) -> RunWindow:
    """Return the WNBA-owned expected window for a scheduled workflow run."""

    if now.tzinfo is None:
        raise ValueError("now must include a timezone")
    if role not in SCHEDULE_WINDOWS_UTC:
        raise ValueError(f"unsupported role: {role}")

    now_utc = now.astimezone(dt.UTC)
    run_date = now_utc.date()
    slate_date = now_utc.astimezone(WNBA_TIME_ZONE).date()
    if role == "dayclose":
        slate_date -= dt.timedelta(days=1)
    start_time, end_time = SCHEDULE_WINDOWS_UTC[role]
    return RunWindow(
        role=role,
        slate_date=slate_date.isoformat(),
        started_at=dt.datetime.combine(run_date, start_time, tzinfo=dt.UTC),
        ended_at=dt.datetime.combine(run_date, end_time, tzinfo=dt.UTC),
    )


def resolve_window(role: str, *, environment: Mapping[str, str], now: dt.datetime) -> RunWindow:
    """Prefer a complete manual window, otherwise derive the scheduled window."""

    values = {
        "slate_date": environment.get("MANUAL_SLATE_DATE", "").strip(),
        "started_at": environment.get("MANUAL_RUN_START_UTC", "").strip(),
        "ended_at": environment.get("MANUAL_RUN_END_UTC", "").strip(),
    }
    supplied = [bool(value) for value in values.values()]
    if any(supplied) and not all(supplied):
        raise ValueError("manual run window inputs must be supplied together")
    if all(supplied):
        return RunWindow.from_strings(role=role, **values)
    return scheduled_window(role, now=now)


def append_github_environment(path: pathlib.Path, window: RunWindow) -> None:
    """Append non-secret run-window values to the GitHub Actions environment file."""

    lines = (
        f"INPUT_SLATE_DATE={window.slate_date}\n"
        f"INPUT_RUN_START_UTC={_iso_utc(window.started_at)}\n"
        f"INPUT_RUN_END_UTC={_iso_utc(window.ended_at)}\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=sorted(SCHEDULE_WINDOWS_UTC), required=True)
    parser.add_argument("--github-env", required=True)
    parser.add_argument("--now-utc", default="")
    args = parser.parse_args()

    now = parse_timestamp(args.now_utc) if args.now_utc else dt.datetime.now(dt.UTC)
    if now is None:
        parser.error("--now-utc must be an ISO-8601 value with a timezone")
    try:
        window = resolve_window(args.role, environment=os.environ, now=now)
    except ValueError as exc:
        parser.error(str(exc))
    append_github_environment(pathlib.Path(args.github_env), window)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
