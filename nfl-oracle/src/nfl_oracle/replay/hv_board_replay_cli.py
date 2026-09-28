"""CLI: score HV/TDV boards with draft-image multipliers and realized values (#597).

Offline and read-only. Walks Corpus C and exported Highest-value boards.
Does not train, does not write the recommendation store, and does not touch
Railway. A separate ``--synthetic`` sweep exercises harness depth when the
full-year corpus is not mounted; those rows are labeled synthetic.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from nfl_oracle.recommendations.hv_boards import discover_hv_label_roots
from nfl_oracle.replay.hv_board_replay import replay_roots, replay_synthetic


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfl-hv-board-replay",
        description=(
            "Score Highest-value / Total Value leaderboards. The target is "
            "the Value column, not draft frequency. Chalk is a comparison "
            "only. Observation only."
        ),
    )
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument("--contest-root", type=Path, default=None)
    parser.add_argument("--export-root", type=Path, default=None)
    parser.add_argument("--board-root", type=Path, default=None)
    parser.add_argument(
        "--synthetic",
        type=int,
        default=0,
        help="Extra deterministic synthetic boards. Reported separately from real boards.",
    )
    parser.add_argument("--seed", type=int, default=597)
    parser.add_argument(
        "--cards",
        action="store_true",
        help="Include per-card multiplier breakdowns.",
    )
    parser.add_argument("--out", type=Path, default=None)
    return parser


def _roots(args: argparse.Namespace) -> tuple[Path, Path, Path | None]:
    if args.project is not None or (
        args.contest_root is None and args.export_root is None and args.board_root is None
    ):
        project = args.project or Path.cwd()
        contest, export, extra = discover_hv_label_roots(project)
    else:
        contest = args.contest_root or Path("data/raw/corpus_c")
        export = args.export_root or Path("data/export/hv_boards")
        extra = args.board_root
    if args.contest_root is not None:
        contest = args.contest_root
    if args.export_root is not None:
        export = args.export_root
    if args.board_root is not None:
        extra = args.board_root
    return contest, export, extra


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    contest, export, extra = _roots(args)
    results, summary = replay_roots(
        contest_root=contest,
        export_root=export,
        board_root=extra,
    )
    synthetic_summary = None
    if args.synthetic:
        _synthetic_results, synthetic_summary = replay_synthetic(args.synthetic, seed=args.seed)
    return {
        "kind": "hv_tdv_board_replay",
        "training_target": "hv_tdv_leaderboard_only",
        "chalk_is_training_target": False,
        "contest_entry": False,
        "railway_mutation": False,
        "draft_law": "realized_value * (slot_multiplier + card_boost)",
        "slot_multipliers": [2.0, 1.8, 1.6, 1.4, 1.2],
        "ollama_candidate": (
            "top five distinct players by displayed_value or highestScore "
            "when present, else value; never draft count"
        ),
        "ridge_label": (
            "realized production on HV/TDV leaderboard rows only. "
            "Not draft frequency. Not the Value column, which the optimizer "
            "multiplies again."
        ),
        "sample_weight_rank": "value_column on leaderboard rows, never draft count",
        "optimizer_objective": "total_value",
        "hv_t40_knobs": (
            "max_value, teams=1, games=1, upside_weight=0, field_weight=0, "
            "boost_rank_blend=0, position_calibration=0"
        ),
        "corpora": {
            "contest_root": str(contest),
            "contest_root_exists": contest.is_dir(),
            "export_root": str(export),
            "export_root_exists": export.is_dir(),
            "board_root": None if extra is None else str(extra),
            "board_root_exists": bool(extra and extra.is_dir()),
        },
        "boards": summary.to_dict(),
        "board_results": [row.to_dict(include_cards=args.cards) for row in results],
        "synthetic": None if synthetic_summary is None else synthetic_summary.to_dict(),
        "synthetic_seed": args.seed if args.synthetic else None,
        "synthetic_n": args.synthetic,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.synthetic < 0:
        print(json.dumps({"status": "error", "error": "synthetic_board_count"}))
        return 2
    report = build_report(args)
    encoded = json.dumps(report, sort_keys=True)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
