"""Offline unit coverage for NFL Corpus G -> matchup corpus append."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "append_game_stats_matchup.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("append_game_stats_matchup", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_append_from_corpus_g_fixture(tmp_path: Path) -> None:
    mod = _load_module()
    season_dir = tmp_path / "corpus_g" / "2002" / "126323"
    season_dir.mkdir(parents=True)
    (season_dir / "stats.json").write_text(
        json.dumps(
            {
                "playerBoxScores": [{"playerId": 10, "value": 3.5}],
                "gameBoxScore": {"homeScore": 21, "awayScore": 17},
            }
        ),
        encoding="utf-8",
    )
    (season_dir / "feed.json").write_text(
        json.dumps(
            {
                "game": {
                    "id": 126323,
                    "day": "2002-09-08",
                    "season": 2002,
                    "week": 1,
                    "status": "final",
                    "homeTeamKey": "SF",
                    "awayTeamKey": "NYG",
                    "homeTeamId": 1,
                    "awayTeamId": 2,
                }
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "matchup_corpus"
    rows = mod.append_from_corpus_g_root(tmp_path / "corpus_g", out)
    assert len(rows) == 1
    assert rows[0]["status"] == "appended"
    matchup = json.loads((out / "nfl" / "2002" / "126323" / "matchup.json").read_text())
    assert matchup["home_team"] == "SF"
    assert matchup["away_team"] == "NYG"
    assert matchup["home_score"] == 21
    # Second pass is idempotent.
    rows2 = mod.append_from_corpus_g_root(tmp_path / "corpus_g", out)
    assert rows2[0]["status"] == "unchanged"
