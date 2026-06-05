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


def _split_last_fold(
    df: pl.DataFrame, name: str, *, date_col: str
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Walk-forward split, using the latest purged+embargoed fold. Falls back to
    a time-ordered 80/20 split when the frame is too short to yield a fold."""
    folds = list(WalkForwardSplitter().split(df, date_col))
    if folds:
        last_train, last_valid = folds[-1]
        train_df, valid_df = df[last_train], df[last_valid]
        log.info(
            "fold_used", corpus=name, train_rows=len(train_df),
            valid_rows=len(valid_df), n_folds=len(folds),
        )
        return train_df, valid_df
    log.warning("no_folds_available_fallback_time_ordered_80_20", corpus=name, rows=len(df))
    ordered = df.sort(date_col)
    cut = int(len(ordered) * 0.8)
    return ordered[:cut], ordered[cut:]


def _load_label_corpus(path: str | None) -> pl.DataFrame:
    if path:
        return pl.read_parquet(Path(path))
    from wnba_oracle.db.reads import read_training_corpus

    return read_training_corpus()


def _load_gamelog_corpus(path: str | None) -> pl.DataFrame:
    from wnba_oracle.features.corpus import build_gamelog_corpus

    if path:
        logs = pl.read_parquet(Path(path))
    else:
        from wnba_oracle.db.reads import read_game_logs

        logs = read_game_logs()
    return build_gamelog_corpus(logs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        default=None,
        help="path to the contest-label corpus (parquet). If omitted, reads slate_labels from Postgres.",
    )
    parser.add_argument(
        "--game-logs",
        default=None,
        help="path to wnba_game_logs (parquet) for the heads corpus. If omitted, reads from Postgres.",
    )
    parser.add_argument(
        "--corpus-mode",
        choices=("gamelog", "label", "both"),
        default="both",
        help="both: heads on the game-log corpus, EB on the contest-label corpus (production). "
        "label: EB-only (reproduces the pre-D63 artifact). gamelog: heads + EB on game logs.",
    )
    parser.add_argument("--commit", default=_git_sha())
    parser.add_argument("--metrics-path", default="/tmp/train_metrics.json")
    args = parser.parse_args()

    configure_logging("INFO")

    label_df = _load_label_corpus(args.corpus) if args.corpus_mode in ("label", "both") else None
    heads_df = (
        _load_gamelog_corpus(args.game_logs)
        if args.corpus_mode in ("gamelog", "both")
        else None
    )
    if args.corpus_mode == "label":
        heads_df = label_df  # heads skip (no target columns); EB-only artifact.
    if args.corpus_mode == "gamelog":
        label_df = heads_df  # EB on the per-game real_score.

    if heads_df is None or heads_df.is_empty():
        log.error("empty_heads_corpus", mode=args.corpus_mode)
        return 2
    log.info("corpus_loaded", mode=args.corpus_mode, heads_rows=len(heads_df),
             label_rows=0 if label_df is None else len(label_df))

    heads_date_col = "slate_date" if args.corpus_mode == "label" else "game_date"
    heads_train, heads_valid = _split_last_fold(heads_df, "heads", date_col=heads_date_col)
    if label_df is not None and not label_df.is_empty():
        label_date_col = "game_date" if args.corpus_mode == "gamelog" else "slate_date"
        label_train, label_valid = _split_last_fold(label_df, "label", date_col=label_date_col)
    else:
        label_train, label_valid = None, None

    art = train_picker(
        heads_train, heads_valid, label_train=label_train, label_valid=label_valid
    )
    path = write_artifact(art, commit=args.commit)

    metrics = {
        "git_sha": args.commit,
        "corpus_mode": args.corpus_mode,
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
