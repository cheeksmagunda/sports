"""Offline map: HV display five vs raw five vs chalk vs the hindsight ceiling.

Reads slate-label CSVs, player-results CSVs, and HV board JSON. Does not
train, does not enter a contest, and does not read draft count as a score.

    uv run --package nfl-oracle nfl-contest-max-map --sport wnba --csv labels.csv
    uv run --package nfl-oracle nfl-contest-max-map --root data/export/hv_boards
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from oracle_core.contest_max import (
    apply_position_csv,
    board_from_hv_json,
    boards_from_csv,
    iter_hv_json_files,
    summarize_boards,
)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def collect_boards(
    *,
    sport: str,
    csv_paths: list[Path],
    roots: list[Path],
    positions_csv: Path | None,
) -> list[dict[str, Any]]:
    positions = None
    if positions_csv is not None:
        positions = apply_position_csv({}, positions_csv.read_text(encoding="utf-8"))
    boards: list[dict[str, Any]] = []
    for path in csv_paths:
        boards.extend(
            boards_from_csv(path.read_text(encoding="utf-8"), sport=sport, positions=positions)
        )
    for root in roots:
        for path in iter_hv_json_files(root):
            payload = _load_json(path)
            if payload is None:
                continue
            board = board_from_hv_json(payload, sport=sport or str(payload.get("sport") or ""))
            if board is not None:
                boards.append(board)
    return boards


def build_report(boards: list[dict[str, Any]], *, sources: list[str]) -> dict[str, Any]:
    return {
        "sources": sources,
        "pool": "board_sections_in_the_supplied_files",
        "excluded_sections": ["My draft", "leaderboard_lineup"],
        "ceiling": "hindsight_optimal_five_on_that_pool",
        "hv_rank_key": "value * (2.0 + card_boost)",
        "chalk": "top five by draft_count on the same pool, score still uses the value law",
        "draft_count_is_label": False,
        "contest_entry": False,
        "summary": summarize_boards(boards),
        "boards": boards,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sport", default="nfl", help="Sport label stored on CSV boards")
    parser.add_argument("--csv", action="append", default=[], type=Path)
    parser.add_argument("--root", action="append", default=[], type=Path)
    parser.add_argument("--positions-csv", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="Write the JSON report here")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Omit per-board rows from stdout (still written to --out when set)",
    )
    args = parser.parse_args(argv)
    if not args.csv and not args.root:
        parser.error("pass at least one --csv or --root")
    boards = collect_boards(
        sport=args.sport,
        csv_paths=list(args.csv),
        roots=list(args.root),
        positions_csv=args.positions_csv,
    )
    sources = [str(path) for path in [*args.csv, *args.root]]
    report = build_report(boards, sources=sources)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    stdout_report = report
    if args.summary_only:
        stdout_report = {key: value for key, value in report.items() if key != "boards"}
    json.dump(stdout_report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
