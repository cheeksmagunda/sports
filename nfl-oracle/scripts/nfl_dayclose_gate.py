#!/usr/bin/env python3
"""Session-free gate: is there an NFL slate inside the day-close sweep window?

Day-close grading and corpus backup both cost nothing to skip on an off day,
but must never skip a day that still needs grading. This checks only the
public nflverse schedule (no Real Sports session, no credentials, safe to
run before any secret exists) for whether the window `nfl-pipeline dayclose
--catchup-window-days` would sweep - `[target_day - (window_days - 1),
target_day]` - contains any non-preseason game date.

Gating on the whole sweep window, not just `target_day` alone, matters: a
Thursday contest that finalizes late leaves Friday's run reporting
"not_finalized", and Saturday has no game the day before. Gating on
yesterday alone would skip Saturday's run entirely and orphan Thursday's
grade until the next game day. Gating on the window instead only ever skips
a real gap - the off-season, or a multi-week bye in the schedule - which is
exactly when skipping is correct.

Attribution: CC BY 4.0 (nflverse / nfldata).
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from nfl_oracle.calendar.schedule import NFLVERSE_SCHEDULE_URL_ALIASES

EASTERN = ZoneInfo("America/New_York")
DEFAULT_WINDOW_DAYS = 7


def default_target_day(now: datetime | None = None) -> date:
    current = now or datetime.now(UTC)
    return (current.astimezone(EASTERN) - timedelta(days=1)).date()


def _download(urls: tuple[str, ...]) -> str:
    last_error: Exception | None = None
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
                return response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
    raise RuntimeError(f"failed to download schedule csv: {last_error}")


def game_days(raw_csv: str) -> set[date]:
    """Every non-preseason `gameday` the schedule reports, as real dates."""

    out: set[date] = set()
    for row in csv.DictReader(io.StringIO(raw_csv)):
        game_type = str(row.get("game_type") or "REG").strip().upper()
        if game_type.startswith("PRE"):
            continue
        raw_day = row.get("gameday")
        if not raw_day:
            continue
        try:
            out.add(date.fromisoformat(raw_day))
        except ValueError:
            continue
    return out


def has_slate_in_window(days: set[date], *, target_day: date, window_days: int) -> bool:
    earliest = target_day - timedelta(days=window_days - 1)
    return any(earliest <= day <= target_day for day in days)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", help="Target day (YYYY-MM-DD); default yesterday in US/Eastern")
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument(
        "--github-output",
        default=os.environ.get("GITHUB_OUTPUT"),
        help="Path to append 'has_slate=true|false' to (GITHUB_OUTPUT in Actions)",
    )
    args = parser.parse_args(argv)

    if args.window_days < 1:
        print("ERROR: --window-days must be at least 1", file=sys.stderr)
        return 1

    target_day = date.fromisoformat(args.day) if args.day else default_target_day()
    days = game_days(_download(NFLVERSE_SCHEDULE_URL_ALIASES))
    found = has_slate_in_window(days, target_day=target_day, window_days=args.window_days)

    print(
        f"has_slate={str(found).lower()} target_day={target_day.isoformat()} "
        f"window_days={args.window_days}"
    )
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            handle.write(f"has_slate={str(found).lower()}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
