"""Unit tests for day-close parquet persist and race corpus aggregate (#338)."""

from __future__ import annotations

import importlib
import sys
from datetime import date
from pathlib import Path

import polars as pl

from nfl_oracle.recommendations.dayclose_persist import (
    build_race_corpus,
    load_dayclose_top_entries,
    persist_dayclose_parquet,
)

DAY = date(2026, 9, 21)
SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _slate_results() -> dict:
    return {
        "contest": {"entrants": 100},
        "law_verified": True,
        "missing_routes": [],
        "top_entries": [
            {
                "contest_id": 2141,
                "entry_id": 1,
                "rank": 1,
                "score": 120.5,
                "payout": 50.0,
                "wager": 5.0,
                "picks": [
                    {"player_id": 10, "slot": 1},
                    {"player_id": 11, "slot": 2},
                ],
            },
            {
                "contest_id": 2141,
                "entry_id": 2,
                "rank": 2,
                "score": 110.0,
                "payout": 20.0,
                "wager": 5.0,
                "picks": [{"player_id": 12, "slot": 1}],
            },
            {
                "contest_id": 2141,
                "entry_id": 99,
                "rank": 25,
                "score": 80.0,
                "payout": 0.0,
                "wager": 5.0,
                "picks": [],
            },
        ],
        "player_draft_stats": [
            {
                "player_id": 10,
                "display_name": "A",
                "team_id": 1,
                "section": "mostDrafted",
                "value": 12.5,
                "draft_count": 100,
                "card_boost": 0.0,
                "avg_score": 20.0,
                "highest_score": 30.0,
            }
        ],
    }


def test_persist_and_load_2026_top_entries(tmp_path: Path) -> None:
    written = persist_dayclose_parquet(
        project_root=tmp_path,
        day=DAY,
        season=2026,
        contest_id=2141,
        slate_results=_slate_results(),
        race_root=tmp_path / "race",
    )
    assert written is not None
    assert Path(written["labels"]).is_file()
    assert Path(written["leaderboards"]).is_file()

    loaded = load_dayclose_top_entries(tmp_path, season=2026, race_root=tmp_path / "race")
    assert loaded.height == 3
    assert set(loaded["rank"].to_list()) == {1, 2, 25}
    assert loaded.filter(pl.col("rank") == 1)["entry_id"].item() == 1


def test_persist_skips_when_slate_results_missing(tmp_path: Path) -> None:
    assert (
        persist_dayclose_parquet(
            project_root=tmp_path,
            day=DAY,
            season=2026,
            contest_id=2141,
            slate_results=None,
            race_root=tmp_path / "race",
        )
        is None
    )


def test_build_race_corpus_aggregates_and_tops_n(tmp_path: Path) -> None:
    persist_dayclose_parquet(
        project_root=tmp_path,
        day=DAY,
        season=2026,
        contest_id=2141,
        slate_results=_slate_results(),
        race_root=tmp_path / "race",
    )
    out = tmp_path / "out"
    summary = build_race_corpus(tmp_path, out, [2026], race_root=tmp_path / "race", top_n=2)
    assert summary == {"2026": {"labels": 1, "leaderboards": 2}}
    boards = pl.read_parquet(out / "leaderboards_2026.parquet")
    assert boards.height == 2
    assert boards["rank"].max() == 2
    labels = pl.read_parquet(out / "labels_2026.parquet")
    assert labels.height == 1
    assert labels["player_id"].item() == 10


def test_resolve_context_snapshot_prefers_explicit_and_newest(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        module = importlib.import_module("resolve_context_snapshot")
        resolve = importlib.reload(module).resolve_context_snapshot
    finally:
        sys.path.remove(str(SCRIPTS))

    context_dir = tmp_path / "data" / "artifacts" / "context"
    context_dir.mkdir(parents=True)
    only = context_dir / "snapshot.json"
    only.write_text("{}", encoding="utf-8")
    assert resolve(tmp_path) == only

    override = tmp_path / "explicit.json"
    override.write_text("{}", encoding="utf-8")
    assert resolve(tmp_path, explicit=str(override)) == override
    assert resolve(tmp_path / "missing") is None
