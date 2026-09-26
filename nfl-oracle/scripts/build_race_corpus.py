"""Build per-season NFL race corpora from day-close parquet drops.

Reads ``data/race/dayclose/<season>/*_{labels,leaderboards}.parquet`` written
by nightly day-close (#338) and aggregates them into
``labels_<season>.parquet`` / ``leaderboards_<season>.parquet`` under
``--output-dir``. Offline and store-free: it only needs the on-disk day
parquet the grade job already persisted.

Example::

    uv run --package nfl-oracle python scripts/build_race_corpus.py \\
        --project-root . --output-dir /tmp/nfl-race --seasons 2025,2026
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

import polars as pl

from nfl_oracle.common.paths import resolve_project_root
from nfl_oracle.recommendations.dayclose_persist import (
    DEFAULT_RACE_ROOT,
    load_dayclose_top_entries,
    race_dayclose_root,
)


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
            temporary_path.unlink(missing_ok=True)


def _load_season_labels(race_root: Path, season: int) -> pl.DataFrame:
    season_dir = race_root / str(season)
    empty = pl.DataFrame(
        schema={
            "slate_date": pl.Utf8,
            "contest_id": pl.Int64,
            "player_id": pl.Int64,
            "display_name": pl.Utf8,
            "team_id": pl.Int64,
            "section": pl.Utf8,
            "value": pl.Float64,
            "draft_count": pl.Int64,
            "card_boost": pl.Float64,
            "avg_score": pl.Float64,
            "highest_score": pl.Float64,
        }
    )
    if not season_dir.is_dir():
        return empty
    frames = [
        pl.read_parquet(path)
        for path in sorted(season_dir.glob("*_labels.parquet"))
        if path.is_file()
    ]
    if not frames:
        return empty
    return pl.concat(frames, how="vertical_relaxed")


def build_race_corpus(
    project_root: Path,
    output_dir: Path,
    seasons: list[int],
    *,
    race_root: Path | None = None,
    top_n: int = 20,
) -> dict[str, dict[str, int]]:
    """Aggregate day-close parquet into per-season race files."""

    if top_n < 1:
        raise ValueError("top_n must be at least 1")
    root = race_dayclose_root(project_root, race_root=race_root)
    summary: dict[str, dict[str, int]] = {}
    for season in seasons:
        labels = _load_season_labels(root, season)
        leaderboards = load_dayclose_top_entries(
            project_root, season=season, race_root=race_root
        )
        if labels.is_empty() and leaderboards.is_empty():
            continue
        if not leaderboards.is_empty():
            leaderboards = leaderboards.filter(pl.col("rank") <= top_n)
        labels_path = output_dir / f"labels_{season}.parquet"
        leaderboards_path = output_dir / f"leaderboards_{season}.parquet"
        _atomic_write_parquet(labels_path, labels)
        _atomic_write_parquet(leaderboards_path, leaderboards)
        summary[str(season)] = {
            "labels": labels.height,
            "leaderboards": leaderboards.height,
        }
    return summary


def _parse_seasons(raw: str) -> list[int]:
    seasons: list[int] = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        seasons.append(int(token))
    if not seasons:
        raise ValueError("seasons must list at least one year")
    return seasons


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="nfl-oracle project root (default: resolve from this script)",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--race-root",
        type=Path,
        default=None,
        help=f"Day-close parquet root (default: <project>/{DEFAULT_RACE_ROOT})",
    )
    parser.add_argument(
        "--seasons",
        required=True,
        help="Comma-separated seasons, e.g. 2025,2026",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Keep leaderboard rows with rank <= N (default: 20)",
    )
    args = parser.parse_args(argv)
    project_root = args.project_root or resolve_project_root(__file__)
    try:
        seasons = _parse_seasons(args.seasons)
        summary = build_race_corpus(
            project_root,
            args.output_dir,
            seasons,
            race_root=args.race_root,
            top_n=args.top_n,
        )
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
