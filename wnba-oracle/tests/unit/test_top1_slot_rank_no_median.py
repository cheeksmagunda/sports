"""PAYOUT_REGIME=top_1 must never rank freeze slots by median finish (#505 / #453).

Cash / top_20 construction may use p50 rearrangement. Draft-win (top_1)
forces ceiling (p90) even when OPTIMIZER_CEILING_TILT_SLOTS is off, and
committed-order scoring uses the same quantile so the objective matches
the frozen slot order.
"""

from __future__ import annotations

import numpy as np

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import (
    OptimizeConfig,
    _committed_rank_quantile,
    _use_ceiling_slot_rank,
    optimize_lineup,
)
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.sample import PlayerSamplingSpec, lineup_score_samples


def test_top_1_forces_ceiling_slot_rank_even_when_tilt_off() -> None:
    cash = default_curve_for_regime("top_20")
    tourney = default_curve_for_regime("top_1")
    cfg_off = OptimizeConfig(ceiling_tilt_slots=False)
    cfg_on = OptimizeConfig(ceiling_tilt_slots=True)

    assert not _use_ceiling_slot_rank(cfg_off, cash)
    assert _use_ceiling_slot_rank(cfg_off, tourney)
    assert _use_ceiling_slot_rank(cfg_on, cash)
    assert _committed_rank_quantile(cfg_off, tourney) == 0.9
    assert _committed_rank_quantile(cfg_off, cash) is None


def test_top_1_slots_high_ceiling_player_over_median_stud() -> None:
    """Player A: high median, low ceiling. Player B: low median, high p90.

    Under top_1 with ceiling_tilt_slots=False (the cash default on bare
    OptimizeConfig), B must still take the 2.0 slot — median ranking is a bug.
    """
    # Forced five-player pool: only slot ORDER can change across regimes.
    # Lognormal on (real_score + K), K=2 (OptimizeConfig.score_offset default).
    # pid 1: median rs ≈ 5, tight. pid 2: median rs ≈ 2, p90 rs ≫ 5.
    specs: list[PlayerSamplingSpec] = []
    fields: list[FieldPlayerSpec] = []
    specs.append(
        PlayerSamplingSpec(
            player_id=1,
            team="LV",
            opponent="NYL",
            mu=float(np.log(7.0)),  # median (rs+K)=7 -> rs≈5
            sigma=0.02,
            boost=0.5,
        )
    )
    fields.append(FieldPlayerSpec(player_id=1, pred_real_score=5.0, card_boost=0.5))
    specs.append(
        PlayerSamplingSpec(
            player_id=2,
            team="NYL",
            opponent="LV",
            mu=float(np.log(4.0)),  # median (rs+K)=4 -> rs≈2
            sigma=0.70,  # p90 (rs+K)≈9.8 -> rs≈7.8 > pid1 p90
            boost=0.5,
        )
    )
    fields.append(FieldPlayerSpec(player_id=2, pred_real_score=2.0, card_boost=0.5))
    for i, rs in enumerate((3.2, 3.0, 2.8)):
        pid = 10 + i
        team = "SEA" if i % 2 == 0 else "MIN"
        opp = "MIN" if team == "SEA" else "SEA"
        specs.append(
            PlayerSamplingSpec(
                player_id=pid,
                team=team,
                opponent=opp,
                mu=float(np.log(rs + 2.0)),
                sigma=0.02,
                boost=0.3,
            )
        )
        fields.append(FieldPlayerSpec(player_id=pid, pred_real_score=rs, card_boost=0.3))

    cfg = OptimizeConfig(
        top_n_filter=5,
        n_samples=3000,
        n_field_lineups=40,
        seed=17,
        max_per_team=5,
        dynamic_team_cap=False,
        ceiling_tilt_slots=False,  # cash knob off — top_1 must still tilt
        objective_mode="payout",
        score_offset=2.0,
    )
    cash = optimize_lineup(specs, fields, default_curve_for_regime("top_20"), cfg=cfg)
    tourney = optimize_lineup(specs, fields, default_curve_for_regime("top_1"), cfg=cfg)

    # Cash/top_20 with tilt off: median stud (pid 1) owns the top slot.
    assert cash.player_ids[0] == 1
    # top_1: ceiling play (pid 2) must claim the 2.0 slot despite tilt knob off.
    assert tourney.player_ids[0] == 2, (
        f"top_1 still ranked by median finish: got {tourney.player_ids}, "
        "expected pid 2 (ceiling) in slot 0"
    )


def test_committed_order_p90_matches_top_1_freeze_key() -> None:
    """Committed-order scoring under top_1 uses p90, same as freeze assembly."""
    rng = np.random.default_rng(3)
    # Player 0: high mean, tight. Player 1: lower mean; >=15% mass in the
    # right tail so sample p90 sits in the high regime (not the bulk).
    n = 400
    low_ceil = rng.normal(4.0, 0.05, size=n)
    high_ceil = np.concatenate(
        [rng.normal(1.8, 0.05, size=int(n * 0.8)), rng.normal(9.0, 0.2, size=int(n * 0.2))]
    )
    samples = np.column_stack(
        [
            low_ceil,
            high_ceil,
            rng.normal(3.0, 0.05, size=n),
            rng.normal(2.8, 0.05, size=n),
            rng.normal(2.6, 0.05, size=n),
        ]
    )
    boosts = np.zeros(5)
    slots = np.array([2.0, 1.8, 1.6, 1.4, 1.2])
    p90_key = np.quantile(samples, 0.9, axis=0)
    mean_key = samples.mean(axis=0)
    assert p90_key[1] > p90_key[0]
    assert mean_key[0] > mean_key[1]
    mean_order = lineup_score_samples(samples, boosts, [0, 1, 2, 3, 4], slots, committed_order=True)
    p90_order = lineup_score_samples(
        samples,
        boosts,
        [0, 1, 2, 3, 4],
        slots,
        committed_order=True,
        committed_rank_quantile=0.9,
    )
    # Different top-slot pairing must change the committed sample path.
    assert not np.allclose(mean_order, p90_order)
