"""``nfl-boost-watch`` — observe when the live card-boost table publishes.

A slate whose boost table reads all zero is not a slate with no leverage; it is
a slate whose leverage has not been published yet. The distinction decides
whether a recommendation is worth freezing, so it is watched explicitly and
recorded with clocks rather than inferred at decision time.

Read-only. One GET per poll against the rating-lineup player search.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from nfl_oracle.contests.boosts import BoostObservation, boost_histogram, observe_boosts
from nfl_oracle.contests.store import project_root
from nfl_oracle.ingest.realsports import (
    BASE,
    capture_live_headers,
    headers_or_capture,
    http_headers,
)

# The search route caps its response; the empty query is the cheapest probe that
# still returns a representative slice of the eligible pool.
PROBE_QUERY = ""


def series_path(override: Path | None = None) -> Path:
    return project_root(override) / "data" / "artifacts" / "boost_watch.jsonl"


async def probe_once(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    contest_id: int,
    day: date,
    query: str = PROBE_QUERY,
) -> tuple[BoostObservation, list[dict[str, Any]]]:
    response = await client.get(
        f"{BASE}/players/sport/nfl/search",
        headers=headers,
        params={
            "query": query,
            "searchType": "ratingLineup",
            "day": day.isoformat(),
            "contestId": contest_id,
            "includeNoOneOption": "false",
        },
        timeout=25,
    )
    response.raise_for_status()
    players = response.json().get("players")
    if not isinstance(players, list):
        raise RuntimeError("search_players_missing")
    captured_at = datetime.now(UTC).isoformat()
    return observe_boosts(contest_id, players, captured_at=captured_at), players


def append_observation(
    path: Path, observation: BoostObservation, *, extra: dict[str, Any] | None = None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = asdict(observation)
    row["contest_entry"] = False
    if extra:
        row.update(extra)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def load_series(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfl-boost-watch",
        description="Watch the live pre-lock card-boost table (read-only).",
    )
    parser.add_argument("--contest-id", type=int, required=True)
    parser.add_argument("--day", required=True, help="contest day, YYYY-MM-DD")
    parser.add_argument("--interval", type=int, default=900, help="seconds between polls")
    parser.add_argument("--until", default=None, help="stop at this UTC ISO timestamp")
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--stop-on-publish",
        action="store_true",
        help="exit as soon as a nonzero boost is observed",
    )
    parser.add_argument("--series", type=Path, default=None)
    return parser


async def _run(args: argparse.Namespace) -> int:
    day = date.fromisoformat(args.day)
    path = args.series or series_path()
    deadline = datetime.fromisoformat(args.until.replace("Z", "+00:00")) if args.until else None
    headers = http_headers(await headers_or_capture())
    published = False
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            try:
                observation, players = await probe_once(
                    client, headers, contest_id=args.contest_id, day=day
                )
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 401:
                    headers = http_headers(await capture_live_headers())
                    continue
                print(json.dumps({"status": "error", "http": error.response.status_code}))
                return 1
            except Exception as error:  # noqa: BLE001 - value-free failure record
                print(json.dumps({"status": "error", "error_type": type(error).__name__}))
                return 1
            histogram = boost_histogram(
                float(p["multiplierBonus"]) for p in players if p.get("multiplierBonus") is not None
            )
            append_observation(path, observation, extra={"histogram": histogram})
            print(
                json.dumps(
                    {
                        "captured_at": observation.captured_at,
                        "contest_id": observation.contest_id,
                        "n_players": observation.n_players,
                        "n_nonzero": observation.n_nonzero,
                        "max_boost": observation.max_boost,
                        "published": observation.published,
                        "histogram": histogram,
                    }
                ),
                flush=True,
            )
            published = observation.published
            if args.once or (published and args.stop_on_publish):
                break
            if deadline is not None and datetime.now(UTC) >= deadline:
                break
            await asyncio.sleep(max(30, args.interval))
    return 0 if published or args.once else 0


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(_run(_parser().parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
