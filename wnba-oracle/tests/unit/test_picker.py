"""Lineup optimizer unit tests."""

from __future__ import annotations

import numpy as np

from wnba_oracle.picker.field import FieldPlayerSpec, project_ownership
from wnba_oracle.picker.optimize import OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import (
    PayoutCurve,
    default_curve_for_regime,
    expected_payout,
)
from wnba_oracle.picker.sample import (
    CopulaConfig,
    PlayerSamplingSpec,
    build_correlation_matrix,
    sample_joint_real_scores,
)


def test_ownership_sums_to_one() -> None:
    specs = [
        FieldPlayerSpec(player_id=i, pred_real_score=float(10 + i), card_boost=0.5 + i * 0.1)
        for i in range(10)
    ]
    own = project_ownership(specs)
    assert abs(float(own.sum()) - 1.0) < 1e-9


def test_default_curve_for_top_regimes() -> None:
    c = default_curve_for_regime("top_1")
    assert c.regime == "top_1"
    assert c.payout_for_rank(0, 1000) >= 10.0  # winners get big
    c20 = default_curve_for_regime("top_20")
    assert c20.payout_for_rank(0, 100) > c20.payout_for_rank(15, 100) > 0


def test_payout_zero_below_cash_line() -> None:
    c = PayoutCurve(percentile_to_payout={0.1: 2.0}, cash_line_percentile=0.1)
    assert c.payout_for_rank(50, 100) == 0.0


def test_correlation_matrix_same_team_negative() -> None:
    specs = [
        PlayerSamplingSpec(1, "LVA", "NYL", mu=0.0, sigma=0.1, boost=0.0),
        PlayerSamplingSpec(2, "LVA", "NYL", mu=0.0, sigma=0.1, boost=0.0),
        PlayerSamplingSpec(3, "NYL", "LVA", mu=0.0, sigma=0.1, boost=0.0),
    ]
    R = build_correlation_matrix(specs, CopulaConfig())
    # Players 1 and 2 are on same team (LVA vs NYL) -> negative
    assert R[0, 1] < 0
    # Players 1 and 3 are on opposing teams in same game -> positive
    assert R[0, 2] > 0


def test_sample_joint_returns_expected_shape() -> None:
    specs = [
        PlayerSamplingSpec(i, "LVA", "NYL", mu=2.0, sigma=0.3, boost=0.5)
        for i in range(5)
    ]
    samples = sample_joint_real_scores(specs, n_samples=200, cfg=CopulaConfig(seed=42))
    assert samples.shape == (200, 5)


def test_expected_payout_with_no_field_is_zero() -> None:
    curve = default_curve_for_regime("top_20")
    own = np.array([10.0, 12.0, 8.0])
    field = np.zeros((0, 3))
    assert expected_payout(own, field, curve) == 0.0


def test_optimizer_returns_lineup_of_size_5() -> None:
    rng = np.random.default_rng(0)
    n = 12
    teams = (["LVA"] * 4) + (["NYL"] * 4) + (["PHO"] * 2) + (["CHI"] * 2)
    opps = (["NYL"] * 4) + (["LVA"] * 4) + (["CHI"] * 2) + (["PHO"] * 2)
    samp_specs = [
        PlayerSamplingSpec(
            player_id=i,
            team=teams[i],
            opponent=opps[i],
            mu=np.log(15.0 + rng.uniform(-5, 5) + 10.0),
            sigma=0.25,
            boost=float(rng.uniform(0, 2)),
        )
        for i in range(n)
    ]
    field_specs = [
        FieldPlayerSpec(
            player_id=i,
            pred_real_score=float(20.0 + rng.uniform(-5, 5)),
            card_boost=samp_specs[i].boost,
        )
        for i in range(n)
    ]
    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(top_n_filter=10, n_samples=200, n_field_lineups=50)
    out = optimize_lineup(samp_specs, field_specs, curve, cfg=cfg)
    assert len(out.player_ids) == 5
    assert len(set(out.player_ids)) == 5
    assert out.lineup_score_p10 <= out.lineup_score_p50 <= out.lineup_score_p90
    assert out.entry_flag in {"enter", "skip", "enter_with_caveat"}
