from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nfl_oracle.replay.backtest import (
    backtest_zero_boost_projection_from_history_index,
    summarize_backtest,
)
from nfl_oracle.valuelaw.candidates import HistoryGame

BASE = datetime(2025, 9, 1, tzinfo=UTC)


def _game(player_id: int, game_id: int, days: int, value: float) -> HistoryGame:
    return HistoryGame(
        season=2025,
        game_id=game_id,
        played_at=BASE + timedelta(days=days),
        position="WR",
        team_id=player_id,
        box_value=value,
        fantasy_points_fanduel=None,
    )


def test_zero_boost_backtest_uses_only_prior_games_and_reports_capture() -> None:
    history = {
        player_id: (
            _game(player_id, 1, 0, float(player_id)),
            _game(player_id, 2, 1, float(player_id + 1)),
            _game(player_id, 3, 2, float(player_id + 2)),
            _game(player_id, 4, 3, float(player_id + 3)),
        )
        for player_id in range(1, 7)
    }
    results = backtest_zero_boost_projection_from_history_index(history, min_player_games=3)
    assert len(results) == 3
    result = results[-1]
    assert result.game_id == 4
    assert result.predicted_player_ids == (6, 5, 4, 3, 2)
    assert result.hindsight_player_ids == (6, 5, 4, 3, 2)
    assert result.capture_ratio == 1.0
    summary = summarize_backtest(results)
    assert summary.n_games == 3
    assert summary.max_capture_ratio == 1.0
    assert summary.mean_capture_ratio is not None and summary.mean_capture_ratio < 1.0
