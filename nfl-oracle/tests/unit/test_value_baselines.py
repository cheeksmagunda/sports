"""Tests for walk-forward Real value baselines (offline)."""

from __future__ import annotations

import json
from pathlib import Path

from nfl_oracle.baselines import HistoricalPriorBaseline, evaluate_walk_forward, regression_metrics
from nfl_oracle.baselines.cli import main as baselines_main
from nfl_oracle.labels import ValueLabel, load_labels_from_corpus_root

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "value_labels"


def _labels() -> list[ValueLabel]:
    return load_labels_from_corpus_root(FIXTURE_ROOT)


def test_position_mean_prior_predicts_train_position_average() -> None:
    train = [
        ValueLabel(player_id=1, game_id=1, season=2022, position="QB", value=4.0),
        ValueLabel(player_id=2, game_id=1, season=2022, position="QB", value=6.0),
        ValueLabel(player_id=3, game_id=1, season=2022, position="RB", value=2.0),
    ]
    model = HistoricalPriorBaseline(kind="position_mean").fit(train)
    assert model.predict_one("QB") == 5.0
    assert model.predict_one("RB") == 2.0
    assert model.predict_one("TE") == model.global_prior


def test_walk_forward_is_oos_by_season_and_reports_pooled_metrics() -> None:
    report = evaluate_walk_forward(_labels())
    assert report.seasons == (2022, 2023, 2024, 2025)
    assert report.n_labels == 21
    test_seasons = sorted({fold.test_season for fold in report.folds})
    assert test_seasons == [2023, 2024, 2025]
    for fold in report.folds:
        assert fold.test_season not in fold.train_seasons
        assert max(fold.train_seasons) < fold.test_season
        assert fold.metrics.n is not None and fold.metrics.n > 0
        assert fold.metrics.mae is not None
    for kind in ("global_mean", "position_mean", "position_median"):
        pooled = report.pooled[kind]
        assert pooled.n == 13  # 2023 (4) + 2024 (4) + 2025 (5)
        assert pooled.mae is not None and pooled.mae >= 0.0
        assert pooled.rmse is not None and pooled.rmse >= pooled.mae - 1e-9


def test_regression_metrics_empty() -> None:
    empty = regression_metrics([], [])
    assert empty.n == 0
    assert empty.mae is None


def test_cli_json_on_fixtures(capsys) -> None:
    code = baselines_main(["--root", str(FIXTURE_ROOT), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["report"]["observation_only"] is True
    assert payload["report"]["contest_entry"] is False
    assert "position_mean" in payload["report"]["pooled"]
    assert payload["report"]["n_labels"] == 21


def test_cli_schema_only(capsys) -> None:
    code = baselines_main(["--schema-only"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "real_value_label"
    assert "same_slate_final_value" in payload["live"]["blacklist"]
