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
