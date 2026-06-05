"""Assemble training_corpus.parquet from Postgres slate_labels.

Thin wrapper around db.reads.read_training_corpus() that writes a local
parquet snapshot for offline convenience. The training CLI (oracle-train)
reads Postgres directly by default; this script is for local inspection.

Writes to data/processed/training_corpus.parquet.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

OUT = Path("data/processed/training_corpus.parquet")
OUT.parent.mkdir(parents=True, exist_ok=True)


def main() -> int:
    from wnba_oracle.db.reads import read_training_corpus

    corpus = read_training_corpus()
    print(f"Source (Postgres): {corpus.height} rows, "
          f"{corpus['slate_date'].n_unique()} slates")
    if corpus.is_empty():
        print("empty corpus; nothing to write")
        return 1
    print(f"Date range: {corpus['slate_date'].min()} .. {corpus['slate_date'].max()}")

    corpus.write_parquet(OUT)
    print(f"\nWrote {OUT}: {corpus.height} rows, {corpus.width} cols")
    print(f"Distinct players: {corpus['player_id'].n_unique()}")
    print(f"Slates: {corpus['slate_date'].n_unique()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
