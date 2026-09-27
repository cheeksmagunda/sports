"""Tests for Real Sports corpus layout + coverage manifest (#526)."""

from __future__ import annotations

import json
from pathlib import Path

from oracle_core.realsports_corpus import (
    append_artifact,
    artifact_path,
    load_coverage_manifest,
    season_from_iso_date,
    slate_or_game_key,
)


def test_layout_paths() -> None:
    assert season_from_iso_date("2026-09-25") == "2026"
    assert slate_or_game_key(slate_date="2026-09-25", contest_id=2100) == ("slate_2026-09-25_2100")
    assert slate_or_game_key(game_id=19457) == "game_19457"
    rel = artifact_path(
        sport="wnba",
        season="2026",
        slate_or_game_id="slate_2026-09-25_2100",
        artifact="hv_board",
    )
    assert str(rel) == "wnba/2026/slate_2026-09-25_2100/hv_board.json"


def test_append_artifact_updates_coverage(tmp_path: Path) -> None:
    summary = append_artifact(
        tmp_path,
        sport="wnba",
        season="2026",
        slate_or_game_id="slate_2026-09-25_2100",
        artifact="hv_board",
        payload={
            "schema_version": 1,
            "sport": "wnba",
            "players": [{"player_id": 1, "value": 12.0}],
            "label": "total_value_leaderboard",
        },
        source="test",
        scraped_at="2026-09-26T12:00:00Z",
    )
    assert summary["path"] == "wnba/2026/slate_2026-09-25_2100/hv_board.json"
    assert summary["wrote"] is True
    board = json.loads((tmp_path / summary["path"]).read_text(encoding="utf-8"))
    assert board["label"] == "total_value_leaderboard"

    # Idempotent second write.
    summary2 = append_artifact(
        tmp_path,
        sport="wnba",
        season="2026",
        slate_or_game_id="slate_2026-09-25_2100",
        artifact="hv_board",
        payload=board,
        source="test",
        scraped_at="2026-09-26T12:00:00Z",
    )
    assert summary2["wrote"] is False

    manifest = load_coverage_manifest(tmp_path)
    key = "wnba/2026/slate_2026-09-25_2100"
    assert key in manifest.entries
    assert "hv_board" in manifest.entries[key].artifacts
    gaps = manifest.gap_report()
    assert gaps and "draft_stats" in gaps[0]["missing_artifacts"]
