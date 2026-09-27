"""Week-3 acceptance: chronological baseline + prediction skeleton."""

from __future__ import annotations

from nhl_oracle.baselines import (
    HistoricalPriorBaseline,
    evaluate_walk_forward,
    regression_metrics,
)
from nhl_oracle.labels import ValueLabel, schema_document


def _label(
    *,
    player_id: int,
    game_id: int,
    season: int,
    position: str,
    value: float,
) -> ValueLabel:
    return ValueLabel(
        player_id=player_id,
        game_id=game_id,
        season=season,
        position=position,
        value=value,
    )


def test_schema_document_is_observation_only() -> None:
    doc = schema_document()
    assert doc["observation_only"] is True
    assert doc["live"]["contest_entry"] is False
    assert doc["goalie_eligible"] is True
    assert "boost_note" in doc["train"]


def test_position_mean_includes_goalie() -> None:
    train = [
        _label(player_id=1, game_id=10, season=2024, position="C", value=10.0),
        _label(player_id=2, game_id=10, season=2024, position="G", value=20.0),
        _label(player_id=3, game_id=11, season=2024, position="G", value=30.0),
    ]
    model = HistoricalPriorBaseline(kind="position_mean").fit(train)
    assert model.position_priors["G"] == 25.0
    assert model.predict_one("G") == 25.0
    assert model.predict_one("D") == model.global_prior


def test_player_mean_falls_back_to_position_then_global() -> None:
    train = [
        _label(player_id=1, game_id=10, season=2024, position="C", value=12.0),
        _label(player_id=2, game_id=10, season=2024, position="RW", value=8.0),
    ]
    model = HistoricalPriorBaseline(kind="player_mean").fit(train)
    assert model.predict_one("C", player_id=1) == 12.0
    assert model.predict_one("C", player_id=99) == 12.0  # position fallback
    assert model.predict_one("D", player_id=99) == model.global_prior


def test_empty_fit_is_honest_zero_predictor() -> None:
    model = HistoricalPriorBaseline(kind="global_mean").fit([])
    assert model.n_train == 0
    assert model.predict_one("G") == 0.0
    metrics = regression_metrics([], [])
    assert metrics.n == 0
    assert metrics.mae is None


def test_walk_forward_report_locks_week3_acceptance() -> None:
    labels = [
        _label(player_id=1, game_id=1, season=2023, position="C", value=5.0),
        _label(player_id=2, game_id=1, season=2023, position="G", value=15.0),
        _label(player_id=1, game_id=2, season=2024, position="C", value=7.0),
        _label(player_id=3, game_id=2, season=2024, position="G", value=11.0),
        _label(player_id=4, game_id=3, season=2025, position="D", value=4.0),
    ]
    report = evaluate_walk_forward(labels)
    payload = report.to_dict()
    assert payload["observation_only"] is True
    assert payload["contest_entry"] is False
    assert payload["boost_regime"] == "none"
    assert payload["n_labels"] == 5
    assert payload["seasons"] == [2023, 2024, 2025]
    assert "global_mean" in payload["baselines"]
    assert "position_mean" in payload["baselines"]
    assert "player_mean" in payload["baselines"]
    # Two OOS folds (2024, 2025) x three baselines
    assert len(report.folds) == 6
    assert report.pooled["global_mean"].n == 3
    assert all(fold.metrics.n > 0 for fold in report.folds)


def test_walk_forward_single_season_has_no_folds() -> None:
    labels = [
        _label(player_id=1, game_id=1, season=2025, position="C", value=5.0),
        _label(player_id=2, game_id=1, season=2025, position="G", value=9.0),
    ]
    report = evaluate_walk_forward(labels)
    assert report.folds == ()
    assert any("Fewer than two seasons" in note for note in report.notes)
    assert report.to_dict()["contest_entry"] is False
