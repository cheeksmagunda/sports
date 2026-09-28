"""advice.json closed loop for the T-40 helper (#574)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from ollama_hv_watcher.advice import (
    build_advice_prompt,
    tilts_from_ollama_notes,
    write_advice,
)
from ollama_hv_watcher.boards import BoardSummary, summarize_board_payload
from ollama_hv_watcher.cli import main as cli_main
from ollama_hv_watcher.learn import build_learn_prompt, run_advice
from ollama_hv_watcher.pick import CHALK_VS_MULTIPLIER_PRINCIPLE
from realsports_corpus.coverage_manifest import build_empty_manifest


def _summary() -> BoardSummary:
    return summarize_board_payload(
        {
            "phase": "pregame",
            "sport": "nfl",
            "slate_key": "2026-09-28",
            "section": "highestBoostedValuePlayers",
            "players": [
                {"player_id": i, "name": f"P{i}", "value": float(80 - i), "team": "T"}
                for i in range(1, 7)
            ],
        },
        mode="pregame",
    )


def test_json_tilts_and_rank_fallback() -> None:
    summary = _summary()
    parsed = tilts_from_ollama_notes(
        json.dumps(
            {
                "tilts": [
                    {"player_id": 1, "mult": 1.4},
                    {"player_id": 99, "mult": 1.1},
                    {"player_id": 2, "mult": 1.0},
                ]
            }
        ),
        summary,
    )
    assert parsed == [{"player_id": 1, "name": "P1", "mult": 1.15}]
    fallback = tilts_from_ollama_notes("not json", summary)
    assert len(fallback) == 5
    assert fallback[0]["player_id"] == 1
    assert fallback[0]["mult"] > 1.0


def test_prompts_state_chalk_principle() -> None:
    summary = _summary()
    assert CHALK_VS_MULTIPLIER_PRINCIPLE in build_advice_prompt(summary)
    assert CHALK_VS_MULTIPLIER_PRINCIPLE in build_learn_prompt(summary)
    assert "real_score" not in build_advice_prompt(summary)


def test_write_advice_and_cli_dry_run(tmp_path: Path) -> None:
    summary = _summary()
    out = write_advice(
        tmp_path,
        summary,
        tilts=[{"player_id": 1, "name": "P1", "mult": 1.05}],
        model="test",
        gate_reason="dry_run",
        dry_run=True,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema"] == "ollama_slate_advice_v1"
    assert payload["sport"] == "nfl"
    assert payload["slate_id"] == "2026-09-28"
    assert payload["tilts"][0]["mult"] == 1.05
    assert "real_score" not in json.dumps(payload)

    board = tmp_path / "hv_board.json"
    board.write_text(
        json.dumps(
            {
                "phase": "pregame",
                "sport": "nfl",
                "slate_key": "2026-09-28",
                "section": "highestBoostedValuePlayers",
                "players": [
                    {
                        "player_id": i,
                        "name": f"P{i}",
                        "value": float(80 - i),
                        "team": "T",
                    }
                    for i in range(1, 7)
                ],
            }
        ),
        encoding="utf-8",
    )
    data_root = tmp_path / "data"
    code = cli_main(["--advice", "--board", str(board), "--data-root", str(data_root)])
    assert code == 0
    written = data_root / "nfl" / "2026-09-28" / "advice.json"
    assert written.is_file()
    body = json.loads(written.read_text(encoding="utf-8"))
    assert body["dry_run"] is True
    assert len(body["tilts"]) == 5


def test_run_advice_fallback_when_generate_fails(tmp_path: Path, monkeypatch) -> None:
    def down(*_a, **_k) -> str:
        raise RuntimeError("ollama_generate_failed")

    monkeypatch.setattr("ollama_hv_watcher.learn.generate", down)
    out = run_advice(
        _summary(),
        data_root=tmp_path,
        manifest=build_empty_manifest(),
        dry_run=False,
        environ={"SPORTS_OLLAMA_UNLOCK": "1"},
        record_on_failure=True,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["extra"]["fallback"] == "rank_tilt"
    assert len(payload["tilts"]) == 5
