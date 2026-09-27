"""Tests for Ollama slate advice writer (#574)."""

from __future__ import annotations

import json
from pathlib import Path

from ollama_hv_watcher.advice import (
    tilts_from_ollama_notes,
    write_advice,
)
from ollama_hv_watcher.boards import summarize_board_payload


def _summary() -> object:
    return summarize_board_payload(
        {
            "sport": "nfl",
            "slate_key": "2026-09-27",
            "label": "test",
            "players": [
                {"player_id": 1, "name": "A", "value": 40.0, "team": "AA"},
                {"player_id": 2, "name": "B", "value": 38.0, "team": "BB"},
                {"player_id": 3, "name": "C", "value": 36.0, "team": "AA"},
                {"player_id": 4, "name": "D", "value": 34.0, "team": "CC"},
                {"player_id": 5, "name": "E", "value": 32.0, "team": "DD"},
            ],
        },
        path="test",
    )


def test_parse_json_tilts_and_write(tmp_path: Path) -> None:
    summary = _summary()
    notes = '{"tilts":[{"player_id":1,"mult":1.1},{"player_id":2,"mult":0.9}]}'
    tilts = tilts_from_ollama_notes(notes, summary)
    assert {t["player_id"] for t in tilts} == {1, 2}
    path = write_advice(
        tmp_path,
        summary,
        tilts=tilts,
        model="test",
        gate_reason="unit",
        dry_run=True,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == "ollama_slate_advice_v1"
    assert payload["slate_id"] == "2026-09-27"
    assert path.name == "advice.json"


def test_fallback_rank_tilts_when_notes_empty() -> None:
    summary = _summary()
    tilts = tilts_from_ollama_notes("not json", summary)
    assert len(tilts) == 5
    assert all(0.85 <= float(t["mult"]) <= 1.15 for t in tilts)
