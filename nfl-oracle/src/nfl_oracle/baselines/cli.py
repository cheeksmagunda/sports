"""Offline CLI for Real value label schema + walk-forward baselines.

Observation only: reads local Corpus G artifacts (or fixtures). Does not
authenticate, does not call Real Sports, and does not enter contests.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nfl_oracle.baselines.priors import BaselineKind
from nfl_oracle.baselines.walk_forward import DEFAULT_BASELINES, evaluate_walk_forward
from nfl_oracle.common.paths import resolve_project_root
from nfl_oracle.labels.extract import load_labels_from_corpus_root
from nfl_oracle.labels.schema import schema_document

ALL_METHODS: tuple[BaselineKind, ...] = (
    "global_mean",
    "position_mean",
    "position_median",
    "player_mean",
)


def default_corpus_root() -> Path:
    project = resolve_project_root(__file__)
    return project / "data" / "raw" / "corpus_g"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfl-value-baselines",
        description=(
            "Offline walk-forward Real value baselines on Corpus G anchors "
            "(shadow / observation only; no contest entry)."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Corpus G raw root (default: nfl-oracle/data/raw/corpus_g)",
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="Print the label schema document and exit.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON (schema + report) instead of a short text summary.",
    )
    parser.add_argument(
        "--methods",
        nargs="+",
        choices=list(ALL_METHODS),
        default=None,
        help=(
            "Baseline methods to evaluate (default: global/position mean+median). "
            "Include player_mean for walk-forward player priors with position/global fallback."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    schema = schema_document()
    if args.schema_only:
        print(json.dumps(schema, indent=2, sort_keys=True))
        return 0

    root = args.root if args.root is not None else default_corpus_root()
    labels = load_labels_from_corpus_root(root)
    methods: tuple[BaselineKind, ...]
    if args.methods:
        methods = tuple(args.methods)
    else:
        methods = DEFAULT_BASELINES
    report = evaluate_walk_forward(labels, baselines=methods)
    payload = {
        "schema": schema,
        "root": str(root),
        "methods": list(methods),
        "report": report.to_dict(),
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print("nfl-value-baselines (observation only; no contest entry)")
    print(f"root: {root}")
    print(f"methods: {list(methods)}")
    print(f"labels: {report.n_labels} across seasons {list(report.seasons)}")
    for kind, metrics in report.pooled.items():
        print(
            f"pooled[{kind}]: n={metrics.n} mae={metrics.mae} "
            f"rmse={metrics.rmse} bias={metrics.bias}"
        )
    for note in report.notes:
        print(f"note: {note}")
    if report.n_labels == 0:
        print(
            "No labels found. Pass --root to fixtures or ingest Corpus G locally.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
