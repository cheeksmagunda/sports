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


def test_blowout_makes_bench_pair_positively_correlated() -> None:
    # Two bench players on the same team in a likely blowout share one
    # garbage-time regime, so their residuals flip from cannibalization to
    # positive (D57). A 2-player same-team matrix is exactly PSD, so the off-
    # diagonal equals the regime-switched rho with no shrinkage.
    cfg = CopulaConfig()
    bench = [
        PlayerSamplingSpec(
            1, "LVA", "NYL", mu=0.0, sigma=0.1, boost=3.0, is_starter=False, blowout_prob=1.0
        ),
        PlayerSamplingSpec(
            2, "LVA", "NYL", mu=0.0, sigma=0.1, boost=3.0, is_starter=False, blowout_prob=1.0
        ),
    ]
    R = build_correlation_matrix(bench, cfg)
    assert R[0, 1] > 0
    assert abs(R[0, 1] - cfg.rho_bench_bench_blowout) < 1e-9


def test_blowout_makes_starter_bench_more_negative() -> None:
    # Starter sits as the bench plays: substitution pushes their correlation
    # below the close-game cannibalization baseline.
    cfg = CopulaConfig()
    pair = [
        PlayerSamplingSpec(
            1, "LVA", "NYL", mu=0.0, sigma=0.1, boost=0.0, is_starter=True, blowout_prob=1.0
        ),
        PlayerSamplingSpec(
            2, "LVA", "NYL", mu=0.0, sigma=0.1, boost=3.0, is_starter=False, blowout_prob=1.0
        ),
    ]
    R = build_correlation_matrix(pair, cfg)
    assert R[0, 1] < cfg.rho_same_team
    assert abs(R[0, 1] - cfg.rho_starter_bench_blowout) < 1e-9


def test_blowout_prob_interpolates_same_team_rho() -> None:
    # At blowout_prob 0.5 the rho is halfway between the close-game baseline
    # and the role-specific blowout target.
    cfg = CopulaConfig()
    half = [
        PlayerSamplingSpec(
            1, "LVA", "NYL", mu=0.0, sigma=0.1, boost=3.0, is_starter=False, blowout_prob=0.5
        ),
        PlayerSamplingSpec(
            2, "LVA", "NYL", mu=0.0, sigma=0.1, boost=3.0, is_starter=False, blowout_prob=0.5
        ),
    ]
    R = build_correlation_matrix(half, cfg)
    expected = 0.5 * cfg.rho_same_team + 0.5 * cfg.rho_bench_bench_blowout
    assert abs(R[0, 1] - expected) < 1e-9


def test_sample_joint_returns_expected_shape() -> None:
    specs = [PlayerSamplingSpec(i, "LVA", "NYL", mu=2.0, sigma=0.3, boost=0.5) for i in range(5)]
    samples = sample_joint_real_scores(specs, n_samples=200, cfg=CopulaConfig(seed=42))
    assert samples.shape == (200, 5)


def test_expected_payout_with_no_field_is_zero() -> None:
    curve = default_curve_for_regime("top_20")
    own = np.array([10.0, 12.0, 8.0])
    field = np.zeros((0, 3))
    assert expected_payout(own, field, curve) == 0.0


def test_caveat_is_skip_defaults_off_and_field_round_trips() -> None:
    """OptimizeConfig.caveat_is_skip defaults to False (preserve current
    behavior) and accepts True without disturbing the rest of the config."""
    assert OptimizeConfig().caveat_is_skip is False
    cfg = OptimizeConfig(caveat_is_skip=True)
    assert cfg.caveat_is_skip is True
    # Other defaults unchanged
    assert cfg.top_n_filter == 30
    assert cfg.max_per_team == 2


def test_caveat_is_skip_demotes_marginal_ev_to_skip() -> None:
    """When best_ev falls in [skip_if, caveat_if), caveat_is_skip=True
    must produce entry_flag='skip' instead of 'enter_with_caveat'."""
    rng = np.random.default_rng(7)
    # Pool deliberately weak so EV lands in the caveat band of a top_20
    # regime. Low mu (-> small real_score) keeps lineup totals below the
    # cash line for most field draws.
    n = 10
    teams = (["LVA"] * 3) + (["NYL"] * 3) + (["PHO"] * 2) + (["CHI"] * 2)
    opps = (["NYL"] * 3) + (["LVA"] * 3) + (["CHI"] * 2) + (["PHO"] * 2)
    samp_specs = [
        PlayerSamplingSpec(
            player_id=i,
            team=teams[i],
            opponent=opps[i],
            mu=np.log(1.5 + rng.uniform(-0.3, 0.3) + 10.0),
            sigma=0.20,
            boost=0.5,
        )
        for i in range(n)
    ]
    field_specs = [
        FieldPlayerSpec(player_id=i, pred_real_score=2.0 + rng.uniform(-0.5, 0.5), card_boost=0.5)
        for i in range(n)
    ]
    curve = default_curve_for_regime("top_20")
    common = {"top_n_filter": 10, "n_samples": 300, "n_field_lineups": 80}
    # Bracket the skip/caveat thresholds around the realized EV so the base
    # lineup lands in the marginal band deterministically -- otherwise this test
    # silently passed via the no-op else branch whenever the pool's EV drifted
    # out of the band (the pool actually scores in the 'skip' band by default).
    ev = optimize_lineup(
        samp_specs, field_specs, curve, cfg=OptimizeConfig(**common)
    ).expected_payout
    band = {
        "skip_if_expected_payout_below": ev - 0.1,
        "caveat_if_expected_payout_below": ev + 0.1,
    }
    base = optimize_lineup(samp_specs, field_specs, curve, cfg=OptimizeConfig(**common, **band))
    flipped = optimize_lineup(
        samp_specs,
        field_specs,
        curve,
        cfg=OptimizeConfig(**common, **band, caveat_is_skip=True),
    )
    # Same player selection regardless of flag policy (EV ordering unchanged).
    assert base.player_ids == flipped.player_ids
    # Precondition: base really is in the caveat band (fail loud if it drifts).
    assert base.entry_flag == "enter_with_caveat"
    # caveat_is_skip demotes that marginal lineup to 'skip'.
    assert flipped.entry_flag == "skip"


def test_never_skip_defaults_off_in_library_config() -> None:
    """OptimizeConfig.never_skip defaults to False so a bare config keeps
    the legacy three-state behavior; production opts in via Settings."""
    assert OptimizeConfig().never_skip is False
    assert OptimizeConfig(never_skip=True).never_skip is True


def test_never_skip_promotes_skip_to_caveat() -> None:
    """never_skip=True must never produce entry_flag='skip'. A weak,
    negative-EV pool that lands in the 'skip' band under the default
    config must surface as 'enter_with_caveat' instead, with identical
    player selection and expected_payout (only the flag policy changes)."""
    rng = np.random.default_rng(7)
    # Same deliberately weak pool as the caveat_is_skip test so the base
    # config lands below the cash line.
    n = 10
    teams = (["LVA"] * 3) + (["NYL"] * 3) + (["PHO"] * 2) + (["CHI"] * 2)
    opps = (["NYL"] * 3) + (["LVA"] * 3) + (["CHI"] * 2) + (["PHO"] * 2)
    samp_specs = [
        PlayerSamplingSpec(
            player_id=i,
            team=teams[i],
            opponent=opps[i],
            mu=np.log(1.5 + rng.uniform(-0.3, 0.3) + 10.0),
            sigma=0.20,
            boost=0.5,
        )
        for i in range(n)
    ]
    field_specs = [
        FieldPlayerSpec(player_id=i, pred_real_score=2.0 + rng.uniform(-0.5, 0.5), card_boost=0.5)
        for i in range(n)
    ]
    curve = default_curve_for_regime("top_20")
    common = {"top_n_filter": 10, "n_samples": 300, "n_field_lineups": 80}
    base = optimize_lineup(samp_specs, field_specs, curve, cfg=OptimizeConfig(**common))
    no_skip = optimize_lineup(
        samp_specs, field_specs, curve, cfg=OptimizeConfig(never_skip=True, **common)
    )
    # Pure flag policy: same players, same EV.
    assert base.player_ids == no_skip.player_ids
    assert base.expected_payout == no_skip.expected_payout
    # Precondition: this weak pool really lands in the 'skip' band by default
    # (fail loud if it drifts), so the promotion below is actually exercised.
    assert base.entry_flag == "skip"
    # never_skip promotes that 'skip' to 'enter_with_caveat' and never emits skip.
    assert no_skip.entry_flag == "enter_with_caveat"


def test_never_skip_overrides_caveat_is_skip() -> None:
    """never_skip wins over caveat_is_skip: a marginal slate that
    caveat_is_skip would demote to 'skip' is promoted back to caveat."""
    rng = np.random.default_rng(7)
    n = 10
    teams = (["LVA"] * 3) + (["NYL"] * 3) + (["PHO"] * 2) + (["CHI"] * 2)
    opps = (["NYL"] * 3) + (["LVA"] * 3) + (["CHI"] * 2) + (["PHO"] * 2)
    samp_specs = [
        PlayerSamplingSpec(
            player_id=i,
            team=teams[i],
            opponent=opps[i],
            mu=np.log(1.5 + rng.uniform(-0.3, 0.3) + 10.0),
            sigma=0.20,
            boost=0.5,
        )
        for i in range(n)
    ]
    field_specs = [
        FieldPlayerSpec(player_id=i, pred_real_score=2.0 + rng.uniform(-0.5, 0.5), card_boost=0.5)
        for i in range(n)
    ]
    curve = default_curve_for_regime("top_20")
    out = optimize_lineup(
        samp_specs,
        field_specs,
        curve,
        cfg=OptimizeConfig(
            top_n_filter=10,
            n_samples=300,
            n_field_lineups=80,
            caveat_is_skip=True,
            never_skip=True,
        ),
    )
    assert out.entry_flag != "skip"


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
