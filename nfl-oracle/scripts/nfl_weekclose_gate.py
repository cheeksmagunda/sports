#!/usr/bin/env python3
"""Session-free gate: should the NFL week-close job run now?

Sibling to `nfl_dayclose_gate.py`. Day-close grades one frozen slate against
finalized results. Week-close runs once per NFL week, about an hour after the
week's final slate ends, and produces a single prioritized punch list.

Live contract (issue #165):

- Derive the week's final game from the public nflverse schedule (never
  hardcode Monday): latest kickoff in the week wins.
- Require that game's scores/result on a live schedule download (finalized).
- Require now >= kickoff + 3h game floor + 1h buffer (exact whistle is not in
  the public feed; scores still gate long OT games).
- Emit GitHub Actions outputs for the workflow and for day-close supersede.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime

from nfl_oracle.calendar.schedule import NFLVERSE_SCHEDULE_URL_ALIASES
from nfl_oracle.calendar.week_close import (
    default_as_of,
    evaluate_gate,
    parse_week_games,
)


def _download(urls: tuple[str, ...]) -> str:
    last_error: Exception | None = None
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
                return response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
    raise RuntimeError(f"failed to download schedule csv: {last_error}")


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
        "--now",
        help="Override wall clock as ISO-8601 (for tests / dispatch); default utcnow",
    )
    parser.add_argument(
        "--github-output",
        default=os.environ.get("GITHUB_OUTPUT"),
        help="Path to append gate outputs to (GITHUB_OUTPUT in Actions)",
    )
    args = parser.parse_args(argv)

    as_of = date.fromisoformat(args.as_of) if args.as_of else default_as_of()
    now = datetime.fromisoformat(args.now) if args.now else None
    if now is not None and now.tzinfo is None:
        from datetime import UTC

        now = now.replace(tzinfo=UTC)

    games = parse_week_games(_download(NFLVERSE_SCHEDULE_URL_ALIASES))
    decision = evaluate_gate(games, as_of=as_of, now=now)
    outputs = decision.as_outputs()

    print(" ".join(f"{key}={value if value != '' else '-'}" for key, value in outputs.items()))
    _write_outputs(args.github_output, outputs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
