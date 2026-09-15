"""Production fit must not activate player_prior (name chalk)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nfl_oracle.recommendations.model import HistoricalPerformance, fit_model
from nfl_oracle.recommendations.schema import EvidenceClock


def _row(
    *,
    player_id: int,
    game_id: int,
    kickoff: datetime,
    value: float,
    position: str = "WR",
) -> HistoricalPerformance:
    # Labels must be postgame (available_at after kickoff).
    available = kickoff + timedelta(hours=2)
    captured = kickoff + timedelta(hours=3)
    return HistoricalPerformance(
        player_id=player_id,
        game_id=game_id,
        kickoff_at=kickoff,
        available_at=available,
        captured_at=captured,
        value=value,
        position=position,
        role=position,
        opportunity=1.0,
        did_not_play=False,
        context_features={"is_divisional": 0.0, "team_pace_prior": 1.0},
        context_clock=EvidenceClock(source_available_at=available, captured_at=captured),
        context_evidence_mode="retrospective_reconstructed",
    )


def test_fit_model_never_activates_player_prior() -> None:
    # Build chronological depth so holdout exists. One player dominates value
    # so a naive player_prior baseline would look strong on MAE; production
    # must still refuse to activate name memorization.
    start = datetime(2024, 9, 1, 17, tzinfo=UTC)
    rows: list[HistoricalPerformance] = []
    for week in range(12):
        kickoff = start + timedelta(days=7 * week)
        for player_id, base in ((1, 3.5), (2, 1.0), (3, 1.2), (4, 0.8)):
            noise = 0.05 * ((week + player_id) % 3)
            rows.append(
                _row(
                    player_id=player_id,
                    game_id=1000 + week,
                    kickoff=kickoff,
                    value=base + noise,
                )
            )
    model = fit_model(rows, trained_at=start + timedelta(days=90))
    assert model.selected_estimator != "player_prior"
    assert model.selected_estimator in {"ridge", "position_mean", "global_mean"}
    assert "player_prior_mae" in model.evaluation
    assert model.evaluation["high_tv_sample_weighting"]
    assert model.feature_names[1] == "player_mean_shrunk"
