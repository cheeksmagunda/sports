"""Total-draft-value sim on Ollama learn ticks (#620)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from ollama_hv_watcher.boards import summarize_board_payload
from ollama_hv_watcher.learn import write_learning_tick
from ollama_hv_watcher.pick import lineup_for_summary
from ollama_hv_watcher.sim import committed_total_value, total_value_lineup


def _players() -> list[dict]:
    rows = []
    for index, value in enumerate((5.0, 4.0, 3.0, 2.0, 1.5, 1.0), start=1):
        rows.append(
            {
                "player_id": index,
                "name": f"P{index}",
                "team": "A",
                "value": value,
                "card_boost": 0.0,
            }
        )
    rows[-1]["card_boost"] = 30.0
    rows[-1]["value"] = 1.0
    return rows


def test_sim_keeps_high_boost_player_box_rank_would_drop() -> None:
    players = _players()
    card = total_value_lineup(players, sport="nfl")
    ids = [row["player_id"] for row in card]
    assert 6 in ids
    assert card[0]["slot"] == 1
    assert committed_total_value(card, sport="nfl") > 0


def test_nhl_sim_zeros_boost() -> None:
    players = _players()
    nfl = total_value_lineup(players, sport="nfl")
    nhl = total_value_lineup(players, sport="nhl")
    assert 6 in [row["player_id"] for row in nfl]
    assert 6 not in [row["player_id"] for row in nhl]
    assert all(row["card_boost"] == 0.0 for row in nhl)


def test_tick_records_sim_and_does_not_publish(tmp_path: Path) -> None:
    summary = summarize_board_payload(
        {
            "sport": "nfl",
            "slate_key": "2026-09-28",
            "section": "highestBoostedValuePlayers",
            "players": _players(),
        }
    )
    card = lineup_for_summary(summary)
    assert 6 in [row["player_id"] for row in card]
    out = write_learning_tick(
        tmp_path,
        summary,
        notes="annotate the sim",
        model="llama3.2:3b",
        gate_reason="operator_unlock",
        dry_run=True,
        lineup=card,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["lineup_source"] == "total_draft_value_sim"
    assert payload["sim"]["objective"] == "total_draft_value"
    assert payload["sim"]["publishes_lineup"] is False
    assert payload["sim"]["lineup_total_value"] > 0
    assert payload["notes"] == "annotate the sim"
