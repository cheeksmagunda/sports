"""Offline unit coverage for WNBA game-stats matchup append."""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "append_game_stats_matchup.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("wnba_append_game_stats_matchup", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_matchup_from_game_log_rows_sets_home_away_and_pace() -> None:
    mod = _load_module()
    rows = [
        {
            "game_id": "1022600999",
            "season": "2026",
            "game_date": "2026-09-20",
            "player_id": 1,
            "player_name": "A Player",
            "team": "LVA",
            "opponent": "SEA",
            "home_away": "H",
            "min": 30,
            "pts": 20,
            "reb": 5,
            "oreb": 1,
            "dreb": 4,
            "ast": 4,
            "stl": 1,
            "blk": 0,
            "tov": 2,
            "fgm": 8,
            "fga": 16,
            "fg3m": 2,
            "ftm": 2,
            "fta": 2,
        },
        {
            "game_id": "1022600999",
            "season": "2026",
            "game_date": "2026-09-20",
            "player_id": 2,
            "player_name": "B Player",
            "team": "SEA",
            "opponent": "LVA",
            "home_away": "A",
            "min": 28,
            "pts": 18,
            "reb": 4,
            "oreb": 0,
            "dreb": 4,
            "ast": 3,
            "stl": 0,
            "blk": 1,
            "tov": 1,
            "fgm": 7,
            "fga": 14,
            "fg3m": 1,
            "ftm": 3,
            "fta": 4,
        },
    ]
    record, stats = mod.matchup_from_game_log_rows(rows, captured_at="2026-09-27T00:00:00+00:00")
    assert record.home_team == "LVA"
    assert record.away_team == "SEA"
    assert record.is_final is True
    assert record.pace is not None
    assert len(stats["players"]) == 2


def test_append_from_csv_idempotent(tmp_path: Path) -> None:
    mod = _load_module()
    csv_path = tmp_path / "game_logs.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "game_id",
                "season",
                "game_date",
                "player_id",
                "player_name",
                "team",
                "opponent",
                "home_away",
                "min",
                "pts",
                "reb",
                "oreb",
                "dreb",
                "ast",
                "stl",
                "blk",
                "tov",
                "fgm",
                "fga",
                "fg3m",
                "ftm",
                "fta",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "game_id": "1",
                "season": "2026",
                "game_date": "2026-09-01",
                "player_id": 9,
                "player_name": "X",
                "team": "NYL",
                "opponent": "CHI",
                "home_away": "H",
                "min": 20,
                "pts": 10,
                "reb": 2,
                "oreb": 1,
                "dreb": 1,
                "ast": 1,
                "stl": 0,
                "blk": 0,
                "tov": 1,
                "fgm": 4,
                "fga": 8,
                "fg3m": 0,
                "ftm": 2,
                "fta": 2,
            }
        )
        writer.writerow(
            {
                "game_id": "1",
                "season": "2026",
                "game_date": "2026-09-01",
                "player_id": 8,
                "player_name": "Y",
                "team": "CHI",
                "opponent": "NYL",
                "home_away": "A",
                "min": 22,
                "pts": 12,
                "reb": 3,
                "oreb": 0,
                "dreb": 3,
                "ast": 2,
                "stl": 1,
                "blk": 0,
                "tov": 2,
                "fgm": 5,
                "fga": 9,
                "fg3m": 1,
                "ftm": 1,
                "fta": 2,
            }
        )
    out = tmp_path / "corpus"
    first = mod.append_from_csv(csv_path, out)
    second = mod.append_from_csv(csv_path, out)
    assert first["appended"] == 1
    assert second["unchanged"] == 1
    assert (out / "wnba" / "2026" / "1" / "matchup.json").is_file()
