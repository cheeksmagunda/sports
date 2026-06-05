"""Training CLI: oracle-train.

Reads labeled training data from Postgres (default) or a parquet file,
splits by walk-forward, trains the multi-task ensemble, runs the
determinism + parity gates, and writes a pickled artifact to models/.

Usage:
    uv run oracle-train                          # reads from Postgres
    uv run oracle-train --corpus path/to/file.parquet  # reads parquet
    uv run oracle-train --commit abc1234 --metrics-path /tmp/train_metrics.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import polars as pl

from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.eval.cv import WalkForwardSplitter
from wnba_oracle.train.pipeline import train_picker, write_artifact

log = get_logger("oracle.train.cli")


def _git_sha() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return r.stdout.strip()[:12]
    except Exception:
        return "no-git"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        default=None,
        help="path to labeled training corpus (parquet). If omitted, reads from Postgres.",
    )
    parser.add_argument("--commit", default=_git_sha())
    parser.add_argument("--metrics-path", default="/tmp/train_metrics.json")
    args = parser.parse_args()

    configure_logging("INFO")

    if args.corpus:
        corpus_path = Path(args.corpus)
        if not corpus_path.exists():
            log.error("missing_corpus", path=str(corpus_path))
            return 2
        df = pl.read_parquet(corpus_path)
        log.info("corpus_loaded", source="parquet", rows=len(df), cols=len(df.columns))
    else:
        from wnba_oracle.db.reads import read_training_corpus

        df = read_training_corpus()
        log.info("corpus_loaded", source="postgres", rows=len(df), cols=len(df.columns))
    if df.is_empty():
        log.error("empty_corpus")
        return 2

    splitter = WalkForwardSplitter()
    folds = list(splitter.split(df))
    if folds:
        # Use the latest fold's split as the final train/valid materialization.
        last_train, last_valid = folds[-1]
        train_df = df[last_train]
        valid_df = df[last_valid]
        log.info(
            "fold_used",
            train_rows=len(train_df),
            valid_rows=len(valid_df),
            n_folds=len(folds),
        )
    else:
        log.warning("no_folds_available_fallback_random_80_20", rows=len(df))
        n = len(df)
        cut = int(n * 0.8)
        train_df = df[:cut]
        valid_df = df[cut:]

    art = train_picker(train_df, valid_df)
    path = write_artifact(art, commit=args.commit)

    metrics = {
        "git_sha": args.commit,
        "training_rows": art.training_rows,
        "low_data_mode": art.low_data_mode,
        "heads": [{"name": k[0], "cohort": k[1]} for k in art.heads],
        "feature_module_sha": art.feature_module_sha,
        "artifact_path": str(path),
    }
    Path(args.metrics_path).write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
