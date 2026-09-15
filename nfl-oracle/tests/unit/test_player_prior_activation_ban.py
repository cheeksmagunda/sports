"""player_prior must not win production activation (#185 / W2 retrain)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nfl_oracle.recommendations.model import EvidenceClock, HistoricalPerformance, fit_model

BASE = datetime(2026, 9, 1, tzinfo=UTC)


def _history() -> list[HistoricalPerformance]:
    rows: list[HistoricalPerformance] = []
    for game in range(20):
        kickoff = BASE + timedelta(days=game)
        clock = EvidenceClock(
            source_available_at=kickoff - timedelta(hours=2),
            captured_at=kickoff - timedelta(hours=1),
        )
        for player, position, role, base in (
            (1, "RB", "rushing", 14.0),
            (2, "RB", "rushing", 3.5),
            (3, "WR", "receiving", 8.0),
            (4, "WR", "receiving", 7.5),
            (5, "QB", "passing", 11.0),
            (6, "TE", "receiving", 5.0),
        ):
            rows.append(
                HistoricalPerformance(
                    player_id=player,
                    game_id=100 + game,
                    position=position,
                    role=role,
                    kickoff_at=kickoff,
                    available_at=kickoff + timedelta(hours=2),
                    captured_at=kickoff + timedelta(hours=3),
                    value=base + (game % 3) * 0.05 * player,
                    opportunity=base,
                    context_features={"weather_index": float(game % 5)},
                    context_clock=clock,
                )
            )
    return rows


def test_fit_model_never_activates_player_prior_even_when_it_wins_holdout_mae() -> None:
    model = fit_model(_history(), trained_at=BASE + timedelta(days=25))
    assert model.selected_estimator != "player_prior"
    assert model.selected_estimator in {"ridge", "position_mean", "global_mean"}
    assert "player_prior_mae" in model.evaluation
