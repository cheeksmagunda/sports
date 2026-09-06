"""CLI: offline walk-forward eval report (baselines vs feature_ridge).

Writes JSON + Markdown under nfl-oracle/artifacts/ by default. Fixture-safe.
Does not authenticate, does not enter contests, does not touch submit gates.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nfl_oracle.baselines.eval_report import (
    COMPARISON_METHODS,
    SAMPLE_STEM,
    build_eval_report,
    default_artifacts_dir,
    default_fixture_root,
    write_eval_report,
)
from nfl_oracle.baselines.priors import BaselineKind
from nfl_oracle.common.paths import resolve_project_root
from nfl_oracle.labels.extract import load_labels_from_corpus_root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfl-walk-forward-report",
        description=(
            "Offline walk-forward evaluation report: classical baselines vs "
            "feature_ridge on Corpus G / fixture labels (observation only)."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help=(
            "Label corpus root (default: tests/fixtures/value_labels). "
            "Pass data/raw/corpus_g for local dense payloads."
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Directory for JSON/MD artifacts (default: nfl-oracle/artifacts).",
    )
    parser.add_argument(
        "--stem",
        default=SAMPLE_STEM,
        help=f"Output filename stem without extension (default: {SAMPLE_STEM}).",
    )
    parser.add_argument(
        "--methods",
        nargs="+",
        choices=list(COMPARISON_METHODS),
        default=None,
        help="Methods to include (default: all classical + feature_ridge).",
    )
    parser.add_argument(
        "--no-latest",
        action="store_true",
        help="Do not also write walk_forward_latest.{json,md}.",
    )
    parser.add_argument(
        "--stdout-json",
        action="store_true",
        help="Also print the full JSON payload to stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root if args.root is not None else default_fixture_root()
    out_dir = args.out_dir if args.out_dir is not None else default_artifacts_dir()
    methods: tuple[BaselineKind, ...]
    if args.methods:
        methods = tuple(args.methods)
    else:
        methods = COMPARISON_METHODS

    labels = load_labels_from_corpus_root(root)
    fixture_mode = root.resolve() == default_fixture_root().resolve()
    # Prefer a portable relative root for checked-in / shared reports.
    root_for_report: Path | str = root
    try:
        project = resolve_project_root(__file__)
        root_for_report = root.resolve().relative_to(project.resolve())
    except ValueError:
        root_for_report = root
    eval_report = build_eval_report(
        labels,
        methods=methods,
        root=root_for_report,
        fixture_mode=fixture_mode,
    )
    paths = write_eval_report(
        eval_report,
        out_dir,
        stem=args.stem,
        also_latest=not args.no_latest,
    )

    print("nfl-walk-forward-report (observation only; no contest entry)")
    print(f"root: {root}")
    print(f"methods: {list(methods)}")
    print(f"labels: {eval_report.report.n_labels} seasons={list(eval_report.report.seasons)}")
    for row in eval_report.ranking_by_mae:
        print(f"rank[{row.kind}]: n={row.n} mae={row.mae} rmse={row.rmse} bias={row.bias}")
    cmp_ = eval_report.feature_ridge_vs_best_baseline
    print(
        "feature_ridge_vs_best_baseline: "
        f"best={cmp_.get('best_baseline')} delta_mae={cmp_.get('delta_mae')} "
        f"ridge_better={cmp_.get('feature_ridge_better')}"
    )
    print(f"wrote: {paths.json_path}")
    print(f"wrote: {paths.md_path}")
    if paths.latest_json:
        print(f"wrote: {paths.latest_json}")
    if paths.latest_md:
        print(f"wrote: {paths.latest_md}")

    if args.stdout_json:
        print(json.dumps(eval_report.to_dict(), indent=2, sort_keys=True))

    if eval_report.report.n_labels == 0:
        print("No labels found under --root.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
