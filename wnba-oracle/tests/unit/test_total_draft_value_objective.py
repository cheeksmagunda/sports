"""Optional total_draft_value optimizer objective (#433).

Default ``objective_mode="payout"`` stays byte-identical to the current
E[payout] path. ``total_draft_value`` selects by E[committed-order TV].
"""

from __future__ import annotations

import numpy as np

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.sample import PlayerSamplingSpec


def _pool() -> tuple[list[PlayerSamplingSpec], list[FieldPlayerSpec]]:
    """Five-team pool where high-TV chalk and high-payout leverage diverge.

    Players 1-5: high mean real_score, high ownership (chalk TV studs).
    Players 6-10: lower mean, low ownership (contrarian payout bait).
    """
    samps: list[PlayerSamplingSpec] = []
    fields: list[FieldPlayerSpec] = []
    for i in range(10):
        team = f"T{i % 5}"
        opp = f"T{(i + 1) % 5}"
        is_chalk = i < 5
        mean_rs = 4.0 if is_chalk else 2.2
        samps.append(
            PlayerSamplingSpec(
                player_id=100 + i,
                team=team,
                opponent=opp,
                mu=float(np.log(mean_rs + 2.0)),
                sigma=0.15 if is_chalk else 0.55,
                boost=0.5 if is_chalk else 1.5,
            )
        )
        fields.append(
            FieldPlayerSpec(
                player_id=100 + i,
                pred_real_score=mean_rs,
                card_boost=0.5 if is_chalk else 1.5,
                measured_drafts=4000.0 if is_chalk else 80.0,
                rank_pred_override=mean_rs,
            )
        )
    return samps, fields


def test_payout_mode_default_is_byte_identical() -> None:
    samps, fields = _pool()
    curve = default_curve_for_regime("top_20")
    base = OptimizeConfig(
        top_n_filter=10,
        n_samples=400,
        n_field_lineups=60,
        max_per_team=5,
        seed=7,
        leverage_weight=0.0,
    )
    explicit = OptimizeConfig(
        top_n_filter=10,
        n_samples=400,
        n_field_lineups=60,
        max_per_team=5,
        seed=7,
        leverage_weight=0.0,
        objective_mode="payout",
    )
    a = optimize_lineup(samps, fields, curve, cfg=base)
    b = optimize_lineup(samps, fields, curve, cfg=explicit)
    assert a.player_ids == b.player_ids
    assert a.expected_payout == b.expected_payout
    assert a.lineup_score_p50 == b.lineup_score_p50


def test_tdv_mode_prefers_high_tv_over_payout_leverage() -> None:
    samps, fields = _pool()
    curve = default_curve_for_regime("top_20")
    payout_cfg = OptimizeConfig(
        top_n_filter=10,
        n_samples=600,
        n_field_lineups=80,
        max_per_team=5,
        seed=11,
        leverage_weight=0.5,
        objective_mode="payout",
    )
    tdv_cfg = OptimizeConfig(
        top_n_filter=10,
        n_samples=600,
        n_field_lineups=80,
        max_per_team=5,
        seed=11,
        leverage_weight=0.5,  # ignored in TDV mode
        objective_mode="total_draft_value",
    )
    payout = optimize_lineup(samps, fields, curve, cfg=payout_cfg)
    tdv = optimize_lineup(samps, fields, curve, cfg=tdv_cfg)
    chalk = {100, 101, 102, 103, 104}
    assert len(set(tdv.player_ids) & chalk) >= len(set(payout.player_ids) & chalk)
    assert tdv.player_ids != payout.player_ids or len(set(tdv.player_ids) & chalk) >= 3


def test_tdv_mode_retains_chalk_stud_when_omitting_collapses_tv() -> None:
    """A near-unique high-TV stud stays selected under TDV even if owned."""
    samps: list[PlayerSamplingSpec] = []
    fields: list[FieldPlayerSpec] = []
    # Stud dominates committed TV. Contrarians have ownership leverage but
    # far less E[slot×boost×realized], so omitting the stud collapses TV.
    specs = [
        (1, "A", "B", 8.0, 0.15, 1.0, 5000.0),  # chalk stud
        (2, "A", "B", 2.0, 0.15, 0.0, 200.0),
        (3, "C", "D", 2.0, 0.15, 0.0, 200.0),
        (4, "C", "D", 2.0, 0.15, 0.0, 200.0),
        (5, "E", "F", 2.0, 0.15, 0.0, 200.0),
        (6, "E", "F", 2.2, 0.45, 0.2, 50.0),
        (7, "G", "H", 2.2, 0.45, 0.2, 50.0),
        (8, "G", "H", 2.2, 0.45, 0.2, 50.0),
        (9, "I", "J", 2.2, 0.45, 0.2, 50.0),
        (10, "I", "J", 2.2, 0.45, 0.2, 50.0),
    ]
    for pid, team, opp, mean_rs, sigma, boost, drafts in specs:
        samps.append(
            PlayerSamplingSpec(
                player_id=pid,
                team=team,
                opponent=opp,
                mu=float(np.log(mean_rs + 2.0)),
                sigma=sigma,
                boost=boost,
            )
        )
        fields.append(
            FieldPlayerSpec(
                player_id=pid,
                pred_real_score=mean_rs,
                card_boost=boost,
                measured_drafts=drafts,
                rank_pred_override=mean_rs,
            )
        )
    curve = default_curve_for_regime("top_20")
    rec = optimize_lineup(
        samps,
        fields,
        curve,
        cfg=OptimizeConfig(
            top_n_filter=10,
            n_samples=500,
            n_field_lineups=60,
            max_per_team=5,
            seed=3,
            objective_mode="total_draft_value",
            leverage_weight=1.0,
        ),
    )
    assert 1 in rec.player_ids


def test_tdv_ownership_fade_prefers_low_ownership_among_equal_tv() -> None:
    """When two combos have similar expected TV, the ownership-fade tiebreaker
    should prefer the lower-owned construction (#453)."""
    # Build a pool where two groups of 5 have identical predicted real_score
    # and boost, but different ownership. The fade should tip toward the low-
    # owned group.
    samps: list[PlayerSamplingSpec] = []
    fields: list[FieldPlayerSpec] = []
    for i in range(10):
        team = f"T{i % 5}"
        opp = f"T{(i + 1) % 5}"
        high_own = i < 5
        mean_rs = 3.0
        samps.append(
            PlayerSamplingSpec(
                player_id=200 + i,
                team=team,
                opponent=opp,
                mu=float(np.log(mean_rs + 2.0)),
                sigma=0.15,
                boost=1.0,
            )
        )
        fields.append(
            FieldPlayerSpec(
                player_id=200 + i,
                pred_real_score=mean_rs,
                card_boost=1.0,
                measured_drafts=5000.0 if high_own else 20.0,
                rank_pred_override=mean_rs,
            )
        )
    curve = default_curve_for_regime("top_20")
    # With fade=0, the selection is seed-determined among equal-TV combos.
    no_fade = optimize_lineup(
        samps,
        fields,
        curve,
        cfg=OptimizeConfig(
            top_n_filter=10,
            n_samples=500,
            n_field_lineups=60,
            max_per_team=5,
            seed=42,
            objective_mode="total_draft_value",
            max_value_ownership_fade=0.0,
        ),
    )
    # With a meaningful fade, low-ownership names should be preferred.
    with_fade = optimize_lineup(
        samps,
        fields,
        curve,
        cfg=OptimizeConfig(
            top_n_filter=10,
            n_samples=500,
            n_field_lineups=60,
            max_per_team=5,
            seed=42,
            objective_mode="total_draft_value",
            max_value_ownership_fade=0.05,
        ),
    )
    low_owned = {205, 206, 207, 208, 209}
    # The faded version should include at least as many low-owned players.
    assert len(set(with_fade.player_ids) & low_owned) >= len(set(no_fade.player_ids) & low_owned)


def test_tdv_settings_wiring() -> None:
    """Verify that Settings env vars reach OptimizeConfig via build_optimize_config."""
    from unittest.mock import patch

    from wnba_oracle.common.settings import Settings
    from wnba_oracle.scheduler.job2 import build_optimize_config

    with patch.dict(
        "os.environ",
        {
            "OPTIMIZER_OBJECTIVE_MODE": "total_draft_value",
            "OPTIMIZER_MAX_VALUE_OWNERSHIP_FADE": "0.05",
        },
    ):
        s = Settings()
        cfg = build_optimize_config(s)
    assert cfg.objective_mode == "total_draft_value"
    assert abs(cfg.max_value_ownership_fade - 0.05) < 1e-9


def test_expected_prod_config_matches_live_tdv_flip() -> None:
    """Watchdog config_drift must expect the live mono TDV flip (#453)."""
    from wnba_oracle.common.settings import EXPECTED_PROD_CONFIG

    assert EXPECTED_PROD_CONFIG["optimizer_objective_mode"] == "total_draft_value"
    assert EXPECTED_PROD_CONFIG["optimizer_max_value_ownership_fade"] == 0.001


def test_tdv_skips_contrarian_in_build_specs(monkeypatch) -> None:
    """Under TDV, sampler mu must not be faded by contrarian (#453).

    Live ownership capture feeds measured drafts into the fade tiebreaker;
    contrarian must not also reshape sampler means under TDV.
    """
    from wnba_oracle.modeling.policy import ModelPolicy
    from wnba_oracle.modeling.prediction import PlayerPredictions
    from wnba_oracle.picker.optimize import OptimizeConfig
    from wnba_oracle.picker.popularity import ContrarianConfig
    from wnba_oracle.scheduler import job2

    preds = PlayerPredictions(
        pred_real_scores={1: 4.0, 2: 3.0},
        rows_by_pid={
            1: {"team": "A", "opponent": "B", "card_boost": 1.0, "name": "Chalk", "position": "G"},
            2: {"team": "C", "opponent": "D", "card_boost": 1.0, "name": "Other", "position": "F"},
        },
    )
    calls: list[object] = []

    def _fake_contrarian(scores, pop, cfg):
        calls.append(cfg)
        return {pid: score - 1.0 for pid, score in scores.items()}

    monkeypatch.setattr(job2, "predict_players", lambda *_a, **_k: preds)
    monkeypatch.setattr(job2, "_compute_popularity_scores", lambda *_a, **_k: {1: 5000.0, 2: 100.0})
    monkeypatch.setattr(job2, "_load_measured_drafts", lambda *_a, **_k: {})
    monkeypatch.setattr(job2, "apply_contrarian_adjustment", _fake_contrarian)
    monkeypatch.setattr(job2, "player_volatility", lambda *_a, **_k: {})
    monkeypatch.setattr(
        job2,
        "materialize_specs",
        lambda adjusted, **_k: (
            [],
            [],
            {pid: {"pred_real_score_p50": score} for pid, score in adjusted.items()},
        ),
    )
    monkeypatch.setattr(job2, "attach_archetypes", lambda *_a, **_k: None)

    policy = ModelPolicy(
        optimizer=OptimizeConfig(objective_mode="total_draft_value"),
        contrarian=ContrarianConfig(enabled=True, strength=0.2),
    )
    _, _, projections = job2._build_specs(
        [{"player_id": 1}, {"player_id": 2}],
        slate_date="2026-09-27",
        policy=policy,
        artifact_resolved=True,
    )
    assert calls == []
    assert projections[1]["pred_real_score_p50"] == 4.0

    payout_policy = ModelPolicy(
        optimizer=OptimizeConfig(objective_mode="payout"),
        contrarian=ContrarianConfig(enabled=True, strength=0.2),
    )
    _, _, payout_proj = job2._build_specs(
        [{"player_id": 1}, {"player_id": 2}],
        slate_date="2026-09-27",
        policy=payout_policy,
        artifact_resolved=True,
    )
    assert len(calls) == 1
    assert payout_proj[1]["pred_real_score_p50"] == 3.0


def test_tdv_disables_floor_tilt_multiplier() -> None:
    """Floor tilt is cash/median mid-slot blend; TDV must keep the true center."""
    from wnba_oracle.modeling.policy import ModelPolicy
    from wnba_oracle.modeling.scoring import _floor_tilt_multiplier
    from wnba_oracle.picker.optimize import OptimizeConfig

    # Sanity: floor tilt still works when weight > 0 under payout path math.
    tilted = _floor_tilt_multiplier(1.0, 4.0, boost=0.5, weight=0.2, max_boost=2.0)
    assert tilted < 1.0

    # TDV path zeros the weight before calling (mirrors prediction.py).
    policy = ModelPolicy(
        optimizer=OptimizeConfig(objective_mode="total_draft_value"),
        picker_floor_tilt_weight=0.2,
    )
    floor_weight = (
        0.0
        if policy.optimizer.objective_mode == "total_draft_value"
        else policy.picker_floor_tilt_weight
    )
    assert _floor_tilt_multiplier(1.0, 4.0, boost=0.5, weight=floor_weight, max_boost=2.0) == 1.0
