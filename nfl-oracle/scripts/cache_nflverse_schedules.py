#!/usr/bin/env python3
"""Download public nflverse/nfldata games.csv and slim into offline schedule cache.

Attribution: CC BY 4.0 (nflverse / nfldata). No Real Sports auth. Observation only.
"""

from __future__ import annotations

import argparse
import csv
import sys
import urllib.error
import urllib.request
from pathlib import Path

from nfl_oracle.calendar.schedule import (
    NFLVERSE_SCHEDULE_URL,
    NFLVERSE_SCHEDULE_URL_ALIASES,
)
from nfl_oracle.common.paths import resolve_project_root
from nfl_oracle.data.paths import resolve_data_paths

KEEP = ("season", "week", "game_id", "gameday", "home_team", "away_team", "game_type")


def _download(urls: tuple[str, ...]) -> bytes:
    last_err: Exception | None = None
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 — public data
                return resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = exc
    raise RuntimeError(f"failed to download schedule csv: {last_err}")


def _slim(raw: str, *, season_min: int, season_max: int) -> list[dict[str, str]]:
    reader = csv.DictReader(raw.splitlines())
    out: list[dict[str, str]] = []
    for row in reader:
        try:
            season = int(row.get("season") or 0)
            week = int(row.get("week") or 0)
        except ValueError:
            continue
        if season < season_min or season > season_max or week <= 0:
            continue
        game_type = str(row.get("game_type") or "REG").strip().upper() or "REG"
        if game_type.startswith("PRE"):
            continue
        out.append({k: str(row.get(k) or "") for k in KEEP})
        out[-1]["game_type"] = game_type
    out.sort(key=lambda r: (int(r["season"]), int(r["week"]), r["game_id"]))
    return out


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(KEEP))
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season-min", type=int, default=2002)
    parser.add_argument("--season-max", type=int, default=2025)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="nfl-oracle project root (default: package resolve)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Reuse existing data/cache/nflverse_games.csv if present",
    )
    args = parser.parse_args(argv)

    root = args.project_root or resolve_project_root(__file__)
    paths = resolve_data_paths(root)
    raw_path = paths.cache / "nflverse_games.csv"
    slim_path = paths.schedule / "schedules.csv"

    if args.skip_download and raw_path.is_file():
        raw_text = raw_path.read_text(encoding="utf-8")
    else:
        blob = _download(NFLVERSE_SCHEDULE_URL_ALIASES)
        paths.cache.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(blob)
        raw_text = blob.decode("utf-8")

    rows = _slim(raw_text, season_min=args.season_min, season_max=args.season_max)
    _write_csv(slim_path, rows)
    seasons = sorted({int(r["season"]) for r in rows})
    print(
        f"cached raw={raw_path} ({raw_path.stat().st_size} bytes) "
        f"slim={slim_path} rows={len(rows)} seasons={seasons[0] if seasons else None}-"
        f"{seasons[-1] if seasons else None} source={NFLVERSE_SCHEDULE_URL}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
