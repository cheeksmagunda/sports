#!/usr/bin/env python3
"""Session-free gate: should the NFL week-close job run now?

Sibling to `nfl_dayclose_gate.py`. Day-close grades one frozen slate against
finalized results. Week-close runs once per NFL week, about an hour after the
week's final slate ends, and produces a single prioritized punch list.

This scaffold:

- Derives the current week's final slate day from the public nflverse
  schedule (never hardcodes Monday).
- Emits GitHub Actions outputs so a workflow can no-op safely.
- Keeps `should_run=false` until live contest/game finalization + 1h buffer
  logic lands (schedule alone cannot know exact whistle time).

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
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from nfl_oracle.calendar.schedule import NFLVERSE_SCHEDULE_URL_ALIASES

EASTERN = ZoneInfo("America/New_York")

# Scaffold: live finalization + 1h buffer is not implemented yet. Keep the
# workflow green and silent until that lands. Schedule-derived identity of the
# final slate day is still computed and tested so day-close coordination can
# build on a stable output contract.
SCAFFOLD_SHOULD_RUN = False
SCAFFOLD_REASON = "scaffold_no_live_finalization_check"


@dataclass(frozen=True)
class WeekFinalSlate:
    season: int
    week: int
    final_gameday: date


def _download(urls: tuple[str, ...]) -> str:
    last_error: Exception | None = None
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
                return response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
    raise RuntimeError(f"failed to download schedule csv: {last_error}")


def parse_week_games(raw_csv: str) -> list[tuple[int, int, date]]:
    """Non-preseason (season, week, gameday) rows from an nflverse schedule CSV."""

    out: list[tuple[int, int, date]] = []
    for row in csv.DictReader(io.StringIO(raw_csv)):
        game_type = str(row.get("game_type") or "REG").strip().upper()
        if game_type.startswith("PRE"):
            continue
        try:
            season = int(row.get("season") or 0)
            week = int(row.get("week") or 0)
        except ValueError:
            continue
        raw_day = (row.get("gameday") or "").strip()
        if season <= 0 or week <= 0 or not raw_day:
            continue
        try:
            gameday = date.fromisoformat(raw_day)
        except ValueError:
            continue
        out.append((season, week, gameday))
    return out


def week_containing(games: list[tuple[int, int, date]], day: date) -> tuple[int, int] | None:
    """Return (season, week) for an exact gameday match, else None."""

    for season, week, gameday in games:
        if gameday == day:
            return season, week
    return None


def final_slate_for_week(
    games: list[tuple[int, int, date]], *, season: int, week: int
) -> WeekFinalSlate | None:
    """Latest gameday in the given season/week is the week's final slate day."""

    days = [gameday for s, w, gameday in games if s == season and w == week]
    if not days:
        return None
    return WeekFinalSlate(season=season, week=week, final_gameday=max(days))


def resolve_week_final(games: list[tuple[int, int, date]], *, as_of: date) -> WeekFinalSlate | None:
    """Final slate for the NFL week that contains `as_of`, if any.

    If `as_of` is not itself a gameday (bye / midweek), look backward up to 6
    days for the most recent gameday and use that week's final slate. This
    keeps a Tuesday / Wednesday poll able to identify Monday's week without
    hardcoding weekday names.
    """

    for offset in range(0, 7):
        candidate = as_of - timedelta(days=offset)
        identity = week_containing(games, candidate)
        if identity is None:
            continue
        season, week = identity
        return final_slate_for_week(games, season=season, week=week)
    return None


def is_final_slate_day(final: WeekFinalSlate | None, day: date) -> bool:
    return final is not None and final.final_gameday == day


def default_as_of(now: datetime | None = None) -> date:
    current = now or datetime.now(UTC)
    return current.astimezone(EASTERN).date()


def _write_outputs(path: str | None, values: dict[str, str]) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as-of",
        help="Calendar day in US/Eastern to evaluate (YYYY-MM-DD); default today Eastern",
    )
    parser.add_argument(
        "--github-output",
        default=os.environ.get("GITHUB_OUTPUT"),
        help="Path to append gate outputs to (GITHUB_OUTPUT in Actions)",
    )
    args = parser.parse_args(argv)

    as_of = date.fromisoformat(args.as_of) if args.as_of else default_as_of()
    games = parse_week_games(_download(NFLVERSE_SCHEDULE_URL_ALIASES))
    final = resolve_week_final(games, as_of=as_of)
    final_day = is_final_slate_day(final, as_of)

    outputs = {
        "should_run": str(SCAFFOLD_SHOULD_RUN).lower(),
        "reason": SCAFFOLD_REASON,
        "as_of": as_of.isoformat(),
        "is_final_slate_day": str(final_day).lower(),
        "season": str(final.season) if final else "",
        "week": str(final.week) if final else "",
        "final_gameday": final.final_gameday.isoformat() if final else "",
    }

    print(" ".join(f"{key}={value if value != '' else '-'}" for key, value in outputs.items()))
    _write_outputs(args.github_output, outputs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
