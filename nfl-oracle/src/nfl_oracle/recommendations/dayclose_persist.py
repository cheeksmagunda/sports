"""Persist day-close Corpus C field results as race-ready parquet.

Nightly grades already embed ``slate_results.top_entries`` and
``player_draft_stats`` inside the ``dayclose_grade`` artifact. The race engine
needs those rows on disk as flat parquet so a subsequent WIN/CLOSE search can
load 2026 (and earlier) finalized contests without re-opening Postgres or the
artifact store. This module is the write path; ``scripts/build_race_corpus.py``
is the aggregate read path.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

DEFAULT_RACE_ROOT = Path("data/race/dayclose")


def race_dayclose_root(project_root: Path, *, race_root: Path | None = None) -> Path:
    root = race_root or (project_root / DEFAULT_RACE_ROOT)
    return root if root.is_absolute() else project_root / root


def day_parquet_paths(race_root: Path, *, season: int, day: date) -> tuple[Path, Path]:
    season_dir = race_root / str(season)
    stamp = day.isoformat()
    return (
        season_dir / f"{stamp}_labels.parquet",
        season_dir / f"{stamp}_leaderboards.parquet",
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


def _labels_frame(day: date, contest_id: int, slate_results: dict[str, Any]) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for stat in slate_results.get("player_draft_stats") or []:
        if not isinstance(stat, dict):
            continue
        rows.append(
            {
                "slate_date": day.isoformat(),
                "contest_id": contest_id,
                "player_id": stat.get("player_id"),
                "display_name": stat.get("display_name"),
                "team_id": stat.get("team_id"),
                "section": stat.get("section"),
                "value": stat.get("value"),
                "draft_count": stat.get("draft_count"),
                "card_boost": stat.get("card_boost"),
                "avg_score": stat.get("avg_score"),
                "highest_score": stat.get("highest_score"),
            }
        )
    schema = {
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
    if not rows:
        return pl.DataFrame(schema=schema)
    return pl.from_dicts(rows, schema=schema)


def _leaderboards_frame(day: date, contest_id: int, slate_results: dict[str, Any]) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for entry in slate_results.get("top_entries") or []:
        if not isinstance(entry, dict):
            continue
        raw_picks = entry.get("picks")
        picks: list[Any] = raw_picks if isinstance(raw_picks, list) else []
        rows.append(
            {
                "slate_date": day.isoformat(),
                "contest_id": contest_id,
                "entry_id": entry.get("entry_id"),
                "rank": entry.get("rank"),
                "score": entry.get("score"),
                "payout": entry.get("payout"),
                "wager": entry.get("wager"),
                "pick_count": len(picks),
                "player_ids": ",".join(
                    str(pick.get("player_id"))
                    for pick in picks
                    if isinstance(pick, dict) and pick.get("player_id") is not None
                ),
            }
        )
    schema = {
        "slate_date": pl.Utf8,
        "contest_id": pl.Int64,
        "entry_id": pl.Int64,
        "rank": pl.Int64,
        "score": pl.Float64,
        "payout": pl.Float64,
        "wager": pl.Float64,
        "pick_count": pl.Int64,
        "player_ids": pl.Utf8,
    }
    if not rows:
        return pl.DataFrame(schema=schema)
    return pl.from_dicts(rows, schema=schema)


def persist_dayclose_parquet(
    *,
    project_root: Path,
    day: date,
    season: int,
    contest_id: int,
    slate_results: dict[str, Any] | None,
    race_root: Path | None = None,
) -> dict[str, str] | None:
    """Write per-day labels + leaderboards parquet. Returns paths or None."""

    if not isinstance(slate_results, dict):
        return None
    root = race_dayclose_root(project_root, race_root=race_root)
    labels_path, leaderboards_path = day_parquet_paths(root, season=season, day=day)
    _atomic_write_parquet(labels_path, _labels_frame(day, contest_id, slate_results))
    _atomic_write_parquet(leaderboards_path, _leaderboards_frame(day, contest_id, slate_results))
    return {
        "labels": str(labels_path),
        "leaderboards": str(leaderboards_path),
    }


def load_dayclose_top_entries(
    project_root: Path,
    *,
    season: int,
    race_root: Path | None = None,
) -> pl.DataFrame:
    """Load every persisted leaderboard parquet for one season (e.g. 2026)."""

    root = race_dayclose_root(project_root, race_root=race_root) / str(season)
    if not root.is_dir():
        return pl.DataFrame(
            schema={
                "slate_date": pl.Utf8,
                "contest_id": pl.Int64,
                "entry_id": pl.Int64,
                "rank": pl.Int64,
                "score": pl.Float64,
                "payout": pl.Float64,
                "wager": pl.Float64,
                "pick_count": pl.Int64,
                "player_ids": pl.Utf8,
            }
        )
    frames = [
        pl.read_parquet(path)
        for path in sorted(root.glob("*_leaderboards.parquet"))
        if path.is_file()
    ]
    if not frames:
        return pl.DataFrame(
            schema={
                "slate_date": pl.Utf8,
                "contest_id": pl.Int64,
                "entry_id": pl.Int64,
                "rank": pl.Int64,
                "score": pl.Float64,
                "payout": pl.Float64,
                "wager": pl.Float64,
                "pick_count": pl.Int64,
                "player_ids": pl.Utf8,
            }
        )
    return pl.concat(frames, how="vertical_relaxed")


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
        leaderboards = load_dayclose_top_entries(project_root, season=season, race_root=race_root)
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
