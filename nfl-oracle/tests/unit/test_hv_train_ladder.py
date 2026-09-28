"""HV board sample weights on the NFL train ladder (#185, #620)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nfl_oracle.recommendations.high_tv import (
    sample_weights_for_history,
    sample_weights_with_hv_boards,
)
from nfl_oracle.recommendations.hv_train import load_hv_train_overlay
from nfl_oracle.recommendations.model import HistoricalPerformance, fit_model

BASE = datetime(2025, 9, 1, 12, tzinfo=UTC)
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "corpus_c_hv"


def _row(player_id: int, game_id: int, value: float, *, day: int = 0) -> HistoricalPerformance:
    kickoff = BASE + timedelta(days=day)
    return HistoricalPerformance(
        player_id=player_id,
        game_id=game_id,
        position="WR",
        kickoff_at=kickoff,
        available_at=kickoff + timedelta(hours=2),
        captured_at=kickoff + timedelta(hours=3),
        value=value,
    )


def test_covered_game_weights_hv_board_not_box_leader() -> None:
    rows = [
        _row(1, 500, 20.0),  # box leader, absent from the HV board
        _row(2, 500, 4.0),
        _row(3, 500, 3.0),
        _row(4, 500, 2.0),
        _row(5, 500, 1.5),
        _row(9, 500, 1.0),  # HV board name, low box value
        _row(8, 700, 12.0),  # uncovered game
        _row(7, 700, 1.0),
    ]
    box = sample_weights_for_history(rows, top_k=1, high_weight=4.0)
    assert box[0] == 4.0
    assert box[5] == 1.0
    weights = sample_weights_with_hv_boards(
        rows,
        {(9, 500): 4.0},
        covered_game_ids=(500,),
        top_k=1,
        high_weight=4.0,
    )
    assert weights[0] == 1.0
    assert weights[5] == 4.0
    assert weights[6] == 4.0  # uncovered game still uses box top-k


def test_load_overlay_uses_hv_section_and_skips_reconstruction(tmp_path: Path) -> None:
    overlay = load_hv_train_overlay(
        corpus_c_root=FIXTURE,
        export_root=tmp_path / "missing-export",
    )
    assert (401, 19457) in overlay.weights
    assert overlay.weights[(401, 19457)] == 4.0
    assert 19457 in overlay.covered_game_ids
    assert 9001 in overlay.contest_ids
    assert 9002 not in overlay.contest_ids


def test_export_file_joins_when_source_is_hv_section(tmp_path: Path) -> None:
    contest = tmp_path / "nfl" / "2025" / "2025-09-15" / "contest_42"
    contest.mkdir(parents=True)
    (contest / "total_value_leaderboard.json").write_text(
        json.dumps(
            {
                "contest_id": 42,
                "section": "highestBoostedValuePlayers",
                "source": "draft_stats.highestBoostedValuePlayers",
                "players": [
                    {"player_id": 9, "value": 3.0, "rank": 1},
                    {"player_id": 1, "value": 30.0, "rank": 2},
                ],
            }
        ),
        encoding="utf-8",
    )
    (contest / "matchups.json").write_text(
        json.dumps({"game_ids": [500]}),
        encoding="utf-8",
    )
    reconstructed = tmp_path / "nfl" / "2025" / "2025-09-16" / "contest_43"
    reconstructed.mkdir(parents=True)
    (reconstructed / "total_value_leaderboard.json").write_text(
        json.dumps(
            {
                "contest_id": 43,
                "section": "highestBoostedValuePlayers",
                "source": "nfl_draft_stats_reconstructed",
                "players": [{"player_id": 1, "value": 99.0}],
            }
        ),
        encoding="utf-8",
    )
    (reconstructed / "matchups.json").write_text(
        json.dumps({"game_ids": [900]}),
        encoding="utf-8",
    )
    overlay = load_hv_train_overlay(
        corpus_c_root=tmp_path / "no-corpus",
        export_root=tmp_path,
    )
    assert overlay.weights[(9, 500)] == 4.0
    assert 900 not in overlay.covered_game_ids
    assert 43 not in overlay.contest_ids


def test_fit_model_records_hv_ladder_when_overlay_is_passed() -> None:
    rows: list[HistoricalPerformance] = []
    for day in range(6):
        for player, value in ((1, 16.0), (2, 4.0), (3, 3.0), (4, 2.0), (5, 1.0), (6, 0.5)):
            rows.append(_row(player, 100 + day, value + day, day=day))
    trained_at = BASE + timedelta(days=8)
    plain = fit_model(rows, trained_at=trained_at)
    assert plain.evaluation["high_tv_sample_weighting"] == ("per_game_top5_value_rank_full_archive")
    covered = fit_model(
        rows,
        trained_at=trained_at,
        hv_weights={(6, 100): 4.0},
        hv_covered_game_ids=(100,),
    )
    assert covered.evaluation["hv_board_games"] >= 1
    assert covered.evaluation["hv_board_weighted_rows"] >= 1
    assert str(covered.evaluation["label_ladder"]).startswith("high_total_value_board")
    assert "hv_board_rank_when_game_linked" in str(covered.evaluation["high_tv_sample_weighting"])
