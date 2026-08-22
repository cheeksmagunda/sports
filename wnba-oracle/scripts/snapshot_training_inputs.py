#!/usr/bin/env python3
"""Snapshot one immutable pair of live training inputs for reproducibility checks."""

from __future__ import annotations

import argparse
from pathlib import Path

from wnba_oracle.db.reads import read_game_logs, read_label_corpus
from wnba_oracle.features.corpus import build_gamelog_corpus


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    labels = read_label_corpus()
    heads = build_gamelog_corpus(read_game_logs())
    if labels.is_empty() or heads.is_empty():
        parser.error("live training inputs must both be non-empty")
    labels.write_parquet(output_dir / "labels.parquet")
    heads.write_parquet(output_dir / "heads.parquet")
    print(f"Training snapshot written: heads={len(heads)} labels={len(labels)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
