"""Assemble training_corpus.parquet from data/historical/slate_labels/.

Schema for oracle-train:
- platform_player_id (kept as 'player_id' for LightGBM categorical)
- real_score (target for EB baseline)
- card_boost (the only useful feature we have)
- position (currently always 'F' — no source data; cohort_for_position
  defaults to F for blanks)
- slate_date (for WalkForwardSplitter)
- team_key (could be useful as future feature)

Writes to data/processed/training_corpus.parquet.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

OUT = Path("data/processed/training_corpus.parquet")
OUT.parent.mkdir(parents=True, exist_ok=True)


def main() -> int:
    sl = pl.read_parquet("data/historical/slate_labels/**/data.parquet")
    print(f"Source: {sl.height} rows, {sl['slate_date'].n_unique()} slates")
    print(f"Date range: {sl['slate_date'].min()} .. {sl['slate_date'].max()}")

    # Drop rows with no real_score (training target)
    sl = sl.drop_nulls("real_score")
    print(f"After dropping null real_score: {sl.height} rows")

    # Build training corpus. LightGBM categorical_features wants 'player_id'.
    # Position is unknown — default to F. Pipeline filters by cohort so this
    # will route everyone to the F head.
    corpus = sl.select([
        pl.col("slate_date").alias("slate_date"),
        pl.col("platform_player_id").alias("player_id"),
        pl.col("display_name"),
        pl.col("team_key").alias("team"),
        pl.col("card_boost"),
        pl.col("real_score"),
        pl.lit("F").alias("position"),  # placeholder; we have no source for real position
    ])

    # WalkForwardSplitter wants slate_date sortable
    corpus = corpus.sort("slate_date")
    corpus.write_parquet(OUT)
    print(f"\nWrote {OUT}: {corpus.height} rows, {corpus.width} cols")
    print(f"Distinct players: {corpus['player_id'].n_unique()}")
    print(f"Slates: {corpus['slate_date'].n_unique()}")
    print(f"low_data_mode threshold is 2000 rows — we have {corpus.height}, so model will train in FULL mode" if corpus.height >= 2000 else f"low_data_mode threshold is 2000 rows — we have {corpus.height}, FALLBACK hyperparameters")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
