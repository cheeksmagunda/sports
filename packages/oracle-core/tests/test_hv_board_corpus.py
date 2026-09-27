"""Tests for durable HV board corpus layout helpers (issue #526)."""

from __future__ import annotations

import json
from pathlib import Path

from oracle_core.hv_board_corpus import (
    HvBoardPlayer,
    append_hv_board,
    build_hv_board,
    year_from_slate_date,
)


def test_year_from_slate_date() -> None:
    assert year_from_slate_date("2026-09-25") == 2026


def test_append_hv_board_writes_json_and_manifest(tmp_path: Path) -> None:
    players = [
        HvBoardPlayer(
            player_id=2,
            name="B Player",
            team="NYL",
            real_score=10.0,
            base=None,
            card_boost=1.5,
            slot=None,
            drafts=100,
            value=15.0,
        ),
        HvBoardPlayer(
            player_id=1,
            name="A Player",
            team="LVA",
            real_score=20.0,
            base=None,
            card_boost=0.5,
            slot=2,
            drafts=50,
            value=30.0,
        ),
    ]
    doc = build_hv_board(
        sport="wnba",
        slate_date="2026-09-25",
        contest_id=2100,
        players=players,
        scraped_at="2026-09-26T12:00:00Z",
    )
    summary = append_hv_board(doc, tmp_path)
    assert summary["player_count"] == 2
    assert summary["path"] == "wnba/2026/slate_2026-09-25_2100/hv_board.json"

    board_path = tmp_path / summary["path"]
    payload = json.loads(board_path.read_text(encoding="utf-8"))
    assert payload["section"] == "highestBoostedValuePlayers"
    assert payload["label"] == "total_value_leaderboard"
    assert payload["players"][0]["player_id"] == 1  # higher value first
    assert payload["players"][0]["value"] == 30.0
    assert set(payload["players"][0]) == {
        "player_id",
        "name",
        "team",
        "real_score",
        "base",
        "card_boost",
        "slot",
        "drafts",
        "value",
    }

    manifest = json.loads((tmp_path / "coverage" / "manifest.json").read_text(encoding="utf-8"))
    assert "wnba/2026/slate_2026-09-25_2100" in manifest["entries"]
    assert "hv_board" in manifest["entries"]["wnba/2026/slate_2026-09-25_2100"]["artifacts"]
