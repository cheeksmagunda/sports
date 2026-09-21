#!/usr/bin/env python3
"""Scheduled NFL T-40 freeze watchdog.

Uses the public nflverse schedule for today's kickoff times plus the durable
recommendation store for freeze/run state. No provider session required.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from oracle_core.storage import PoolOptions, create_postgres_engine

from nfl_oracle.calendar.schedule import NFLVERSE_SCHEDULE_URL_ALIASES
from nfl_oracle.calendar.week_close import parse_week_games
from nfl_oracle.recommendations.store import RecommendationStore
from nfl_oracle.recommendations.watchdog import evaluate_t40_deadline, render_markdown

EASTERN = ZoneInfo("America/New_York")


def default_target_day(now: datetime | None = None) -> date:
    current = now or datetime.now(UTC)
    return current.astimezone(EASTERN).date()


def _download(urls: tuple[str, ...]) -> str:
    last_error: Exception | None = None
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
                return response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
    raise RuntimeError(f"failed_to_download_schedule_csv: {type(last_error).__name__}")


def _engine():
    value = os.environ.get("NFL_DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("NFL_DATABASE_URL_required")
    return create_postgres_engine(
        value,
        pool=PoolOptions(pool_size=2, max_overflow=1, pool_timeout=5),
        connect_args={"connect_timeout": 5},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", help="Target day (YYYY-MM-DD); default today in US/Eastern")
    parser.add_argument("--grace-minutes", type=int, default=10)
    parser.add_argument("--report", help="Optional markdown report path")
    parser.add_argument(
        "--github-output",
        default=os.environ.get("GITHUB_OUTPUT"),
        help="Path to append key=value outputs to",
    )
    args = parser.parse_args(argv)

    if args.grace_minutes < 0:
        print("ERROR: --grace-minutes must be non-negative", file=sys.stderr)
        return 1

    day = date.fromisoformat(args.day) if args.day else default_target_day()
    raw_schedule = _download(NFLVERSE_SCHEDULE_URL_ALIASES)
    games = parse_week_games(raw_schedule)
    store = RecommendationStore(_engine())
    report = evaluate_t40_deadline(
        day=day,
        games=games,
        frozen=store.latest(day),
        latest_run=store.latest_run(day),
        checked_at=datetime.now(UTC),
        grace_minutes=args.grace_minutes,
    )
    markdown = render_markdown(report)
    if args.report:
        Path(args.report).write_text(markdown, encoding="utf-8")
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as handle:
            handle.write(f"status={report.status}\n")
            handle.write(f"reason={report.reason}\n")
            handle.write(f"day={report.day.isoformat()}\n")
    print(f"status={report.status} reason={report.reason} day={report.day.isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
