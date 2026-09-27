"""Tests for season backfill cursor resume."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from nfl_oracle.ingest.backfill import (
    TRACKED_SEASONS,
    BackfillCursor,
    load_cursor,
    load_season_game_ids,
    save_cursor,
)
from nfl_oracle.ingest.corpus_g import CorpusGStore


def test_cursor_round_trip(tmp_path: Path) -> None:
    store = CorpusGStore(root=tmp_path)
    cursor = BackfillCursor(
        season=2002,
        last_game_id=126323,
        completed_game_ids=[126323],
    )
    save_cursor(store, cursor)
    loaded = load_cursor(store)
    assert loaded.season == 2002
    assert loaded.last_game_id == 126323
    assert loaded.completed_game_ids == [126323]
    assert loaded.updated_at


def test_load_season_game_ids_explicit_and_catalog(tmp_path: Path) -> None:
    catalog = tmp_path / "season_game_ids.json"
    catalog.write_text(json.dumps({"2002": [126323]}), encoding="utf-8")
    assert load_season_game_ids(2002, catalog_path=catalog) == [126323]
    assert load_season_game_ids(2002, explicit=[9, 8]) == [9, 8]


def test_tracked_seasons_runs_through_the_current_utc_year() -> None:
    """TRACKED_SEASONS must not go stale every season (#338): it should track
    the running UTC year rather than a hardcoded upper bound."""
    assert TRACKED_SEASONS[0] == 2002
    assert TRACKED_SEASONS == tuple(range(2002, datetime.now(UTC).year + 1))
    assert TRACKED_SEASONS[-1] == datetime.now(UTC).year
    # Strictly increasing, contiguous, no gaps.
    assert list(TRACKED_SEASONS) == list(range(TRACKED_SEASONS[0], TRACKED_SEASONS[-1] + 1))
