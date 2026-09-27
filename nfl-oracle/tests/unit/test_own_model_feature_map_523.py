"""Phase-1 (#523): own-model ridge consumes safe live_ok slate context."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nfl_oracle.baselines.value_model import (
    CONTEXT_FEATURE_NAMES,
    MODEL_FEATURE_NAMES,
    FeatureDrivenValueModel,
)
from nfl_oracle.features.live import (
    REQUIRED_LIVE_OK_CONTEXT_FEATURES,
    REQUIRED_SLATE_CONTEXT_FEATURES,
    kickoff_slot_features,
    kickoff_slot_name,
)
from nfl_oracle.features.own_model_map import (
    assert_no_unclassified_live_ok,
    classify_feature,
    own_model_gap_matrix,
)
from nfl_oracle.labels.schema import ValueLabel
from nfl_oracle.recommendations.model import (
    REQUIRED_LIVE_OK_CONTEXT_FEATURES as PROD_REQUIRED,
)
from nfl_oracle.recommendations.model import (
    HistoricalPerformance,
    _context_feature_names,
    fit_model,
)
from nfl_oracle.recommendations.schema import EvidenceClock

BASE = datetime(2025, 9, 7, 17, tzinfo=UTC)  # Sunday early ET


def _lab(
    pid: int,
    season: int,
    pos: str,
    value: float,
    *,
    context: dict[str, float] | None = None,
) -> ValueLabel:
    return ValueLabel(
        player_id=pid,
        game_id=season * 1000 + pid,
        season=season,
        position=pos,
        value=value,
        team_id=1,
        context_features=context or {},
    )


def test_required_slate_keys_are_force_included() -> None:
    for key in (
        "is_home",
        "home_away",
        "is_divisional",
        "days_rest",
        "opponent_adjusted_prior",
        "opp_def_value_allowed_prior",
        "team_pace_prior",
        "opponent_pace_prior",
        "kickoff_slot_early",
    ):
        assert key in REQUIRED_LIVE_OK_CONTEXT_FEATURES
        assert key in REQUIRED_SLATE_CONTEXT_FEATURES
    assert set(REQUIRED_SLATE_CONTEXT_FEATURES) <= set(REQUIRED_LIVE_OK_CONTEXT_FEATURES)
    assert PROD_REQUIRED == REQUIRED_LIVE_OK_CONTEXT_FEATURES


def test_production_fit_keeps_slate_keys_without_dense_history() -> None:
    rows = []
    for game in range(6):
        kickoff = BASE + timedelta(days=game)
        for player in range(1, 7):
            rows.append(
                HistoricalPerformance(
                    player_id=player,
                    game_id=100 + game,
                    position="WR",
                    role="receiving",
                    kickoff_at=kickoff,
                    available_at=kickoff + timedelta(hours=2),
                    captured_at=kickoff + timedelta(hours=3),
                    value=float(player + game),
                    opportunity=float(player + game),
                    did_not_play=False,
                    context_features={},
                    context_clock=None,
                )
            )
    model = fit_model(rows, trained_at=BASE + timedelta(days=10))
    for key in REQUIRED_SLATE_CONTEXT_FEATURES:
        assert key in model.context_feature_names
    for key in REQUIRED_LIVE_OK_CONTEXT_FEATURES:
        assert key in model.context_feature_names


def test_feature_ridge_includes_player_prior_median_and_context_slots() -> None:
    train = [
        _lab(1, 2022, "QB", 10.0, context={"is_home": 1.0, "is_divisional": 1.0}),
        _lab(2, 2022, "RB", 4.0, context={"is_home": 0.0, "team_pace_prior": 55.0}),
        _lab(1, 2023, "QB", 12.0, context={"is_home": 1.0, "days_rest": 7.0}),
        _lab(2, 2023, "RB", 5.0, context={"is_home": 0.0, "opp_def_value_allowed_prior": 9.0}),
    ]
    model = FeatureDrivenValueModel(alpha=0.5).fit(train)
    assert "player_prior_median" in MODEL_FEATURE_NAMES
    assert model.n_features == len(MODEL_FEATURE_NAMES) + 2 * len(CONTEXT_FEATURE_NAMES)
    assert model.context_feature_names == CONTEXT_FEATURE_NAMES
    matrix = model.design_matrix(train)
    assert len(matrix[0]) == model.n_features
    is_home_idx = CONTEXT_FEATURE_NAMES.index("is_home")
    core = len(MODEL_FEATURE_NAMES)
    assert matrix[0][core + 2 * is_home_idx] == 1.0
    assert matrix[0][core + 2 * is_home_idx + 1] == 0.0
    pace_idx = CONTEXT_FEATURE_NAMES.index("team_pace_prior")
    assert matrix[0][core + 2 * pace_idx] == 0.0
    assert matrix[0][core + 2 * pace_idx + 1] == 1.0


def test_feature_ridge_context_moves_prediction_when_coefs_nonzero() -> None:
    train = [
        _lab(1, 2022, "WR", 8.0),
        _lab(2, 2022, "WR", 9.0),
        _lab(3, 2022, "RB", 6.0),
        _lab(1, 2023, "WR", 8.5),
        _lab(2, 2023, "WR", 9.5),
        _lab(3, 2023, "RB", 6.5),
    ]
    model = FeatureDrivenValueModel(alpha=1.0).fit(train)
    coefs = list(model._ridge.coefficients)
    is_home_idx = CONTEXT_FEATURE_NAMES.index("is_home")
    core = len(MODEL_FEATURE_NAMES)
    coefs[core + 2 * is_home_idx] = 5.0
    model._ridge.coefficients = coefs
    home = model.predict([_lab(1, 2024, "WR", 0.0, context={"is_home": 1.0})])[0]
    away = model.predict([_lab(1, 2024, "WR", 0.0, context={"is_home": 0.0})])[0]
    missing = model.predict([_lab(1, 2024, "WR", 0.0)])[0]
    assert home > away
    assert missing != home


def test_kickoff_slot_sunday_early() -> None:
    assert kickoff_slot_name(BASE) == "early"
    feats = kickoff_slot_features(BASE)
    assert feats["kickoff_slot_early"] == 1.0
    assert feats["kickoff_slot_late"] == 0.0


def test_own_model_gap_matrix_covers_live_ok() -> None:
    assert_no_unclassified_live_ok()
    rows = {row["feature"]: row for row in own_model_gap_matrix()}
    assert rows["player_prior_median"]["status"] == "ridge_core"
    assert rows["is_divisional"]["status"] == "context_required"
    assert rows["team_pace_prior"]["status"] == "context_required"
    assert rows["same_slate_final_value"]["status"] == "leakage_blocked"
    assert classify_feature("kickoff_slot") == "context_required"


def test_classify_feature_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unclassified"):
        classify_feature("__not_a_real_feature__")


def test_sparse_observed_still_unions_required() -> None:
    kick = BASE
    rows = [
        HistoricalPerformance(
            player_id=1,
            game_id=1,
            position="WR",
            kickoff_at=kick,
            available_at=kick + timedelta(hours=2),
            captured_at=kick + timedelta(hours=3),
            value=10.0,
            context_features={"depth_rank": 1.0},
            context_clock=EvidenceClock(
                source_available_at=kick - timedelta(hours=1),
                captured_at=kick - timedelta(minutes=30),
            ),
        )
    ]
    names = _context_feature_names(rows)
    assert "depth_rank" in names
    assert "is_home" in names
    assert "opponent_adjusted_prior" in names
    assert "kickoff_slot_snf" in names
