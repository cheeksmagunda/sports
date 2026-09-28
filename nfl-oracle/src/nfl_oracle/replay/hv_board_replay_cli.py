"""CLI: score saved HV boards (HV five vs chalk five vs hindsight).

Offline and read-only. Walks Corpus C on disk. Never authenticates, never
enters a contest, never writes the recommendation store.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nfl_oracle.contests.parse import ContestParseError, iter_contests
from nfl_oracle.contests.store import ContestStore
from nfl_oracle.replay.hv_board_replay import replay_hv_board, summarize_replays


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfl-hv-board-replay",
        description=(
            "Score each Highest-value board: HV-rank five vs draft-count chalk "
            "five vs the hindsight ceiling, under value * (slot + card boost)."
        ),
    )
    parser.add_argument(
        "--contest-root",
        type=Path,
        default=Path("nfl-oracle/data/raw/corpus_c"),
        help="Corpus C root (contest directories). On the worker volume this is "
        "/app/nfl-oracle/data/raw/corpus_c.",
    )
    parser.add_argument("--out", type=Path, default=None, help="Optional JSON report path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.contest_root.expanduser()
    store = ContestStore(root)
    boards = []
    skipped = 0
    for contest in iter_contests(store, finalized_only=True):
        try:
            scored = replay_hv_board(contest)
        except (ContestParseError, ValueError, KeyError, TypeError):
            skipped += 1
            continue
        if scored is None:
            skipped += 1
            continue
        boards.append(scored)
    summary = summarize_replays(boards)
    report = {
        "status": "scored",
        "contest_root": str(root),
        "boards_skipped": skipped,
        **summary,
        "boards": boards,
        "contest_entry": False,
    }
    encoded = json.dumps(report, sort_keys=True)
    print(encoded)
    if args.out is not None:
        args.out.expanduser().write_text(encoded + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
