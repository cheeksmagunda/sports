"""Leakage-safe feature_ridge value model + strategy wiring."""

from __future__ import annotations

import json
from pathlib import Path

from nfl_oracle.baselines.cli import main as baselines_main
from nfl_oracle.baselines.ridge import RidgeRegressor
from nfl_oracle.baselines.value_model import (
    FORBIDDEN_FEATURE_NAMES,
    MODEL_FEATURE_NAMES,
    FeatureDrivenValueModel,
    assert_model_features_leakage_safe,
)
from nfl_oracle.baselines.walk_forward import evaluate_walk_forward
from nfl_oracle.features.schema import live_ok_feature_names
from nfl_oracle.labels import load_labels_from_corpus_root
from nfl_oracle.labels.schema import ValueLabel
from nfl_oracle.strategy import (
    FiveCardAction,
    predict_values_by_player,
    shadow_score_with_feature_model,
    value_model_strategy_note,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "value_labels"


def _lab(
    pid: int,
    season: int,
    pos: str,
    value: float,
    *,
    team_id: int | None = 1,
    game_id: int | None = None,
) -> ValueLabel:
    return ValueLabel(
        player_id=pid,
        game_id=game_id if game_id is not None else season * 1000 + pid,
        season=season,
        position=pos,
        value=value,
        team_id=team_id,
    )


def test_model_features_are_live_ok_and_not_blacklisted() -> None:
    assert_model_features_leakage_safe()
    live = set(live_ok_feature_names())
    for name in MODEL_FEATURE_NAMES:
        assert name not in FORBIDDEN_FEATURE_NAMES
        if name.startswith("pos_") or name == "intercept":
            continue
        assert name in live
    assert "same_slate_final_value" not in MODEL_FEATURE_NAMES
    assert "value" not in MODEL_FEATURE_NAMES


def test_ridge_recovers_simple_signal() -> None:
    # y ≈ 2 * x1 + 3; x0 is intercept column of ones
    x = [[1.0, float(i)] for i in range(10)]
    y = [3.0 + 2.0 * float(i) for i in range(10)]
    model = RidgeRegressor(alpha=1e-6).fit(x, y)
    preds = model.predict(x)
    assert all(abs(p - t) < 0.05 for p, t in zip(preds, y, strict=True))


def test_feature_ridge_ignores_label_value_on_predict() -> None:
    train = [
        _lab(1, 2022, "QB", 10.0),
        _lab(2, 2022, "RB", 4.0),
        _lab(1, 2023, "QB", 12.0),
        _lab(2, 2023, "RB", 5.0),
    ]
    model = FeatureDrivenValueModel(alpha=0.5).fit(train)
    a = _lab(1, 2024, "QB", 0.0)
    b = _lab(1, 2024, "QB", 999.0)  # poisoned label must not affect features
    assert model.predict([a])[0] == model.predict([b])[0]


def test_walk_forward_feature_ridge_no_future_season_in_train() -> None:
    labels = load_labels_from_corpus_root(FIXTURE_ROOT)
    report = evaluate_walk_forward(labels, baselines=("feature_ridge",))
    assert report.n_labels == 21
    assert "feature_ridge" in report.pooled
    for fold in report.folds:
        assert fold.kind == "feature_ridge"
        assert fold.test_season not in fold.train_seasons
        assert max(fold.train_seasons) < fold.test_season
        assert fold.metrics.n is not None and fold.metrics.n > 0


def test_mutating_future_labels_does_not_change_oos_preds() -> None:
    """Classic leakage probe: test-season y must not enter the fit."""

    base = [
        _lab(1, 2020, "QB", 8.0),
        _lab(2, 2020, "RB", 3.0),
        _lab(1, 2021, "QB", 9.0),
        _lab(2, 2021, "RB", 4.0),
        _lab(1, 2022, "QB", 10.0),
        _lab(2, 2022, "RB", 5.0),
    ]
    train = [row for row in base if row.season < 2022]
    test = [row for row in base if row.season == 2022]
    model_a = FeatureDrivenValueModel(alpha=1.0).fit(train)
    preds_a = model_a.predict(test)

    poisoned_test = [
        ValueLabel(
            player_id=row.player_id,
            game_id=row.game_id,
            season=row.season,
            position=row.position,
            value=row.value + 1000.0,
            team_id=row.team_id,
        )
        for row in test
    ]
    # Refit on the same train (unchanged); predict on poisoned rows.
    model_b = FeatureDrivenValueModel(alpha=1.0).fit(train)
    preds_b = model_b.predict(poisoned_test)
    assert preds_a == preds_b

    # If train accidentally included 2022, poisoning train would move coeffs.
    leaked_train = train + poisoned_test
    model_leak = FeatureDrivenValueModel(alpha=1.0).fit(leaked_train)
    preds_leak = model_leak.predict(test)
    assert preds_leak != preds_a


def test_design_matrix_never_contains_raw_label() -> None:
    train = [_lab(1, 2022, "QB", 7.0), _lab(2, 2022, "WR", 3.0), _lab(3, 2022, "RB", 4.0)]
    model = FeatureDrivenValueModel().fit(train)
    test = [_lab(1, 2023, "QB", 12345.0)]
    matrix = model.design_matrix(test)
    assert len(matrix) == 1
    assert 12345.0 not in matrix[0]
    assert matrix[0][0] == 1.0  # intercept


def test_default_walk_forward_omits_feature_ridge() -> None:
    labels = load_labels_from_corpus_root(FIXTURE_ROOT)
    report = evaluate_walk_forward(labels)
    assert "feature_ridge" not in report.baselines
    assert set(report.baselines) == {"global_mean", "position_mean", "position_median"}


def test_cli_feature_ridge_optional(capsys) -> None:
    code = baselines_main(["--root", str(FIXTURE_ROOT), "--methods", "feature_ridge", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["methods"] == ["feature_ridge"]
    assert "feature_ridge" in payload["report"]["pooled"]
    assert payload["report"]["observation_only"] is True
    assert payload["report"]["contest_entry"] is False


def test_cli_default_still_mean_median(capsys) -> None:
    code = baselines_main(["--root", str(FIXTURE_ROOT), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["methods"] == ["global_mean", "position_mean", "position_median"]
    assert "feature_ridge" not in payload["methods"]


def test_strategy_shadow_values_from_feature_model() -> None:
    train = [
        _lab(1, 2022, "QB", 10.0),
        _lab(2, 2022, "RB", 4.0),
        _lab(3, 2022, "WR", 5.0),
        _lab(4, 2022, "TE", 2.0),
        _lab(5, 2022, "K", 1.0),
        _lab(1, 2023, "QB", 11.0),
        _lab(2, 2023, "RB", 4.5),
        _lab(3, 2023, "WR", 5.5),
        _lab(4, 2023, "TE", 2.2),
        _lab(5, 2023, "K", 1.1),
    ]
    players = [(1, "QB"), (2, "RB"), (3, "WR"), (4, "TE"), (5, "K")]
    values = predict_values_by_player(train, players, decision_season=2024)
    assert set(values) == {1, 2, 3, 4, 5}
    assert all(isinstance(v, float) for v in values.values())
    action = FiveCardAction(player_ids=(1, 2, 3, 4, 5), slot_multipliers=(2, 1.8, 1.6, 1.4, 1.2))
    score, mapped = shadow_score_with_feature_model(
        action,
        train,
        {pid: pos for pid, pos in players},
        decision_season=2024,
    )
    assert score.structural_ok
    assert mapped == values
    note = value_model_strategy_note()
    assert note["optional"] is True
    assert note["contest_entry"] is False
