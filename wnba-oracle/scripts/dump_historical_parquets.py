"""Dump the canonical Postgres tables to local parquet snapshots.

Writes:
  data/processed/wnba_game_logs.parquet      from read_game_logs()
  data/historical/slate_labels/slate_date=YYYY-MM-DD/data.parquet  (one per slate)
  data/historical/leaderboards/slate_date=YYYY-MM-DD/data.parquet  (one per slate)

These mirror the layout job1 / job2 / training read locally when DATABASE_URL is
not set, and are the snapshots most analysis notebooks reach for. The training
CLI itself reads Postgres directly; these are for offline convenience and audit.

Usage:
    set -a && source .env && set +a
    export DATABASE_URL="$DATABASE_PUBLIC_URL"
    export PGSSLROOTCERT="$PWD/.pgssl/server.crt"
    uv run python scripts/dump_historical_parquets.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

PROCESSED = Path("data/processed")
HISTORICAL = Path("data/historical")


def _dump_game_logs() -> None:
    from wnba_oracle.db.reads import read_game_logs

    df = read_game_logs()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out = PROCESSED / "wnba_game_logs.parquet"
    df.write_parquet(out)
    n_op = int((df.get_column("opponent").fill_null("") != "").sum()) if "opponent" in df.columns else 0
    print(
        f"wrote {out}: {df.height} rows, {df.width} cols, "
        f"opponent_filled={n_op}/{df.height}, "
        f"games={df.get_column('game_id').n_unique() if 'game_id' in df.columns else 'n/a'}"
    )


def _dump_partitioned(df, root: Path, *, label: str) -> None:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    # Partition manually so the layout matches the historical convention
    # (slate_date=YYYY-MM-DD/data.parquet, single file per slate).
    n_slates = 0
    for slate in df.get_column("slate_date").unique().sort().to_list():
        part = root / f"slate_date={slate}"
        part.mkdir(parents=True, exist_ok=True)
        sub = df.filter(df.get_column("slate_date") == slate)
        sub.write_parquet(part / "data.parquet")
        n_slates += 1
    print(f"{label}: wrote {n_slates} slate partitions under {root}")


def main() -> int:
    from wnba_oracle.db.reads import read_leaderboards, read_slate_labels

    _dump_game_logs()
    _dump_partitioned(read_slate_labels(), HISTORICAL / "slate_labels", label="slate_labels")
    _dump_partitioned(read_leaderboards(), HISTORICAL / "leaderboards", label="leaderboards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
