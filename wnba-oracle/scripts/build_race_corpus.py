"""Build per-season race corpora from the read-only backup Postgres.

Exports full-pool ``slate_labels`` (including realized scores) and top-N
``contest_leaderboards`` rows (with raw ``user_id``) to parquet files named
``labels_<season>.parquet`` and ``leaderboards_<season>.parquet`` under
``--output-dir``. Intended for publication on the orphan ``backups`` branch
alongside the CSV corpus snapshots.

Reads ``BACKUP_DATABASE_URL`` when set, otherwise ``DATABASE_PUBLIC_URL`` or
``DATABASE_URL``. TLS verification is required (see ``corpus_backup_common``).
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

import polars as pl
from corpus_backup_common import portable_postgres_url, require_verified_tls
from seasons_common import add_seasons_argument, parse_seasons
from sqlalchemy import create_engine, text

_LABELS_QUERY = text(
    "SELECT contest_id, slate_date, section, platform_player_id, display_name, "
    "team_key, card_boost, drafts, real_score "
    "FROM slate_labels ORDER BY slate_date, contest_id, platform_player_id"
)
_LEADERBOARDS_QUERY = text(
    "SELECT contest_id, slate_date, entry_id, rank, paged_rank, user_id, score, "
    "lineup::text AS lineup_json, num_brawlers "
    "FROM contest_leaderboards ORDER BY slate_date, contest_id, rank"
)


def _get_backup_engine():
    url = (
        os.environ.get("BACKUP_DATABASE_URL")
        or os.environ.get("DATABASE_PUBLIC_URL")
        or os.environ.get("DATABASE_URL")
    )
    if not url:
        raise RuntimeError("set BACKUP_DATABASE_URL, DATABASE_PUBLIC_URL, or DATABASE_URL")
    require_verified_tls(url)
    return create_engine(
        portable_postgres_url(url),
        connect_args={"options": "-c default_transaction_read_only=on"},
    )


def _read_all_labels(engine) -> pl.DataFrame:
    with engine.connect() as conn:
        rows = conn.execute(_LABELS_QUERY).fetchall()
    if not rows:
        return pl.DataFrame(
            schema={
                "contest_id": pl.Int64,
                "slate_date": pl.Utf8,
                "section": pl.Utf8,
                "platform_player_id": pl.Int64,
                "display_name": pl.Utf8,
                "team_key": pl.Utf8,
                "card_boost": pl.Float64,
                "drafts": pl.Int64,
                "real_score": pl.Float64,
            }
        )
    return pl.from_dicts([dict(r._mapping) for r in rows])


def _read_all_leaderboards(engine) -> pl.DataFrame:
    with engine.connect() as conn:
        rows = conn.execute(_LEADERBOARDS_QUERY).fetchall()
    if not rows:
        return pl.DataFrame(
            schema={
                "contest_id": pl.Int64,
                "slate_date": pl.Utf8,
                "entry_id": pl.Int64,
                "rank": pl.Int64,
                "paged_rank": pl.Int64,
                "user_id": pl.Utf8,
                "score": pl.Float64,
                "lineup_json": pl.Utf8,
                "num_brawlers": pl.Int64,
            }
        )
    return pl.from_dicts([dict(r._mapping) for r in rows])


def _atomic_write_parquet(path: Path, frame: pl.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent, suffix=".parquet"
    )
    os.close(fd)
    temporary_path = Path(temporary_name)
    try:
        frame.write_parquet(temporary_path)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def build_race_corpus(
    output_dir: Path,
    seasons: list[str],
    *,
    top_n: int = 20,
    engine=None,
) -> dict[str, dict[str, int]]:
    """Write per-season parquet files; return row counts per season."""

    if top_n < 1:
        raise ValueError("top_n must be at least 1")
    owns_engine = engine is None
    eng = engine or _get_backup_engine()
    try:
        labels_all = _read_all_labels(eng)
        leaderboards_all = _read_all_leaderboards(eng)
    finally:
        if owns_engine and hasattr(eng, "dispose"):
            eng.dispose()

    summary: dict[str, dict[str, int]] = {}
    for season in seasons:
        prefix = f"{season}-"
        season_labels = labels_all.filter(pl.col("slate_date").str.starts_with(prefix))
        if season_labels.is_empty():
            continue
        season_leaderboards = leaderboards_all.filter(
            pl.col("slate_date").str.starts_with(prefix) & (pl.col("rank") <= top_n)
        )
        labels_path = output_dir / f"labels_{season}.parquet"
        leaderboards_path = output_dir / f"leaderboards_{season}.parquet"
        _atomic_write_parquet(labels_path, season_labels)
        _atomic_write_parquet(leaderboards_path, season_leaderboards)
        summary[season] = {
            "labels": season_labels.height,
            "leaderboards": season_leaderboards.height,
        }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Keep leaderboard rows with rank <= N (default: 20)",
    )
    add_seasons_argument(parser)
    args = parser.parse_args(argv)
    try:
        seasons = parse_seasons(args.seasons)
        summary = build_race_corpus(args.output_dir, seasons, top_n=args.top_n)
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not summary:
        print("ERROR: no seasons produced output", file=sys.stderr)
        return 1
    for season, counts in sorted(summary.items()):
        print(
            f"race corpus {season}: labels={counts['labels']} "
            f"leaderboards={counts['leaderboards']} -> {args.output_dir}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
