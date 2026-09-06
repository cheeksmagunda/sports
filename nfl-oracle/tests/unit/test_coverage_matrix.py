"""Tests for season coverage matrix status vocabulary."""

from __future__ import annotations

from pathlib import Path

from nfl_oracle.ingest.backfill import (
    SEASON_STATUS_KNOWN,
    SEASON_STATUS_UNKNOWN,
    CoverageCell,
    _upsert_coverage,
    load_coverage_matrix,
    refresh_coverage_matrix,
)
from nfl_oracle.ingest.corpus_g import CorpusGStore


def test_refresh_matrix_marks_tracked_seasons_unknown(tmp_path: Path) -> None:
    store = CorpusGStore(root=tmp_path)
    matrix = refresh_coverage_matrix(store)
    assert matrix["seasons"]["2021"]["status"] == SEASON_STATUS_UNKNOWN
    assert "2025" in matrix["seasons"]
    assert "status_vocabulary" in matrix


def test_upsert_marks_season_known_with_value_note(tmp_path: Path) -> None:
    store = CorpusGStore(root=tmp_path)
    cell = CoverageCell(
        season=2024,
        game_id=18800,
        day="2024-11-03",
        status="final",
        box_count=70,
        value_nonnull=70,
        player_count=162,
        play_count=162,
        paths={"stats": "stats.json"},
        ingested_at="2026-09-06T01:00:00+00:00",
        event_time="2024-11-03T18:00:00.000Z",
        source_available_at="2024-11-03T21:25:31.277Z",
        captured_at="2026-09-06T01:00:00Z",
        decision_at=None,
    )
    _upsert_coverage(store, cell)
    matrix = load_coverage_matrix(store)
    block = matrix["seasons"]["2024"]
    assert block["status"] == SEASON_STATUS_KNOWN
    assert block["games_ingested"] == 1
    assert "Real value" in block["value_note"]
    game = block["games"]["18800"]
    assert game["event_time"] == "2024-11-03T18:00:00.000Z"
    assert game["value_note"]
