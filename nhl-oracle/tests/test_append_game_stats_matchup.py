"""NHL public boxscore -> durable matchup corpus append."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "append_game_stats_matchup.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("nhl_append_game_stats_matchup", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_matchup_from_nhl_boxscore(tmp_path: Path) -> None:
    mod = _load_module()
    boxscore = {
        "id": 2024020001,
        "season": 20242025,
        "gameDate": "2024-10-08",
        "gameState": "OFF",
        "gameType": 2,
        "venue": {"default": "Arena"},
        "awayTeam": {"id": 10, "abbrev": "TOR", "score": 2},
        "homeTeam": {"id": 8, "abbrev": "MTL", "score": 3},
        "playerByGameStats": {
            "awayTeam": {
                "forwards": [
                    {
                        "playerId": 1,
                        "name": {"default": "A Forward"},
                        "position": "C",
                        "goals": 1,
                        "assists": 0,
                        "points": 1,
                    }
                ],
                "defense": [],
                "goalies": [],
            },
            "homeTeam": {
                "forwards": [],
                "defense": [],
                "goalies": [],
            },
        },
    }
    record, stats = mod.matchup_from_nhl_boxscore(boxscore, captured_at="2026-09-27T00:00:00+00:00")
    assert record.home_team == "MTL"
    assert record.away_team == "TOR"
    assert record.is_final is True
    assert record.pace is None  # documented gap until team metrics land
    assert len(stats["players"]) == 1
    out = tmp_path / "corpus"
    path = tmp_path / "box.json"
    path.write_text(json.dumps(boxscore), encoding="utf-8")
    summary = mod.append_boxscore_file(path, out)
    assert summary["status"] == "appended"
    assert (out / "nhl" / "20242025" / "2024020001" / "matchup.json").is_file()
