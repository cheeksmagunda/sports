"""Lineup boost caps.

Historical failures showed high-total-boost lineups with thin minutes history
are fragile, so the optimizer supports a lineup-wide boost cap and a per-pick
boost cap.

Two knobs, both default 0.0 = OFF so a bare OptimizeConfig() is unchanged:
  - boost_sum_cap: lineup-wide sum-of-card-boost ceiling
  - max_single_boost: per-pick card_boost ceiling

The optimizer skips any combo violating either; relaxes both to 0 when the
caps + team cap are jointly infeasible (so we NEVER forfeit a slate).
"""

from __future__ import annotations

import numpy as np

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import (
    OptimizeConfig,
    _boost_cap_is_feasible,
    _exceeds_boost_cap,
    optimize_lineup,
)
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.sample import PlayerSamplingSpec

# -- pure cap-check helpers ---------------------------------------------------


def test_exceeds_boost_cap_max_single_only() -> None:
    boosts = np.array([1.0, 2.5, 3.0, 0.5, 1.5])
    assert _exceeds_boost_cap((0, 1, 2, 3, 4), boosts, sum_cap=0.0, max_single=2.5)
    assert not _exceeds_boost_cap((0, 1, 3, 4), boosts, sum_cap=0.0, max_single=2.5)


def test_exceeds_boost_cap_sum_only() -> None:
    boosts = np.array([1.0, 2.0, 3.0, 0.5, 1.5])  # sum 8.0
    assert _exceeds_boost_cap((0, 1, 2, 3, 4), boosts, sum_cap=7.0, max_single=0.0)
    assert not _exceeds_boost_cap((0, 1, 2, 3, 4), boosts, sum_cap=8.0, max_single=0.0)


def test_exceeds_boost_cap_both_zero_never_skips() -> None:
    """Both caps disabled -> _exceeds_boost_cap returns False for any combo."""
    boosts = np.array([3.0, 3.0, 3.0, 3.0, 3.0])
    assert not _exceeds_boost_cap((0, 1, 2, 3, 4), boosts, sum_cap=0.0, max_single=0.0)


def test_boost_cap_feasibility_pool_too_few_below_per_pick_max() -> None:
    """Pool has fewer than 5 players below max_single -> infeasible."""
    boosts = np.array([3.0, 3.0, 3.0, 3.0, 3.0, 3.0])  # all 3.0, max_single 2.5
    assert not _boost_cap_is_feasible(boosts, sum_cap=0.0, max_single=2.5)


def test_boost_cap_feasibility_smallest_five_within_sum() -> None:
    boosts = np.array([0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    # smallest 5 sum to 7.5
    assert _boost_cap_is_feasible(boosts, sum_cap=7.5, max_single=0.0)
    assert not _boost_cap_is_feasible(boosts, sum_cap=7.0, max_single=0.0)


# -- end-to-end optimize_lineup behaviour -------------------------------------


def _spec_pair(
    *, boost_grid: list[float], n_per_team: int = 6, seed: int = 0
) -> tuple[list[PlayerSamplingSpec], list[FieldPlayerSpec]]:
    """Build a 12-player slate (2 teams, 6 each) with the given per-pick boosts.

    pred_real_score is constant 3.0 so picks compete on boost x slot only --
    in the absence of a cap the optimizer prefers the highest-boost combo.
    """
    rng = np.random.default_rng(seed)
    samps: list[PlayerSamplingSpec] = []
    fields: list[FieldPlayerSpec] = []
    for i, b in enumerate(boost_grid):
        team = "LV" if i < n_per_team else "NYL"
        opp = "NYL" if team == "LV" else "LV"
        pid = 100 + i
        # Sampling mu in log space; pred_real_score = 3.0 for the field.
        samps.append(
            PlayerSamplingSpec(
                player_id=pid,
                team=team,
                opponent=opp,
                mu=float(np.log(3.0 + 2.0)),
                sigma=0.2,
                boost=b,
                is_starter=False,
                blowout_prob=0.0,
                is_anchor=False,
            )
        )
        fields.append(FieldPlayerSpec(player_id=pid, pred_real_score=3.0, card_boost=b))
    # Per-team shuffle so input order isn't degenerate.
    rng.shuffle(samps)
    rng.shuffle(fields)
    return samps, fields


def test_optimize_lineup_uncapped_picks_highest_boost() -> None:
    """Baseline: with both caps OFF, the optimizer floors the lineup with 3.0
    boost picks (the documented "value trap" pattern)."""
    boosts = [3.0, 3.0, 3.0, 2.5, 2.0, 1.0, 3.0, 3.0, 3.0, 2.5, 2.0, 1.0]
    samps, fields = _spec_pair(boost_grid=boosts)
    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(
        top_n_filter=12,
        n_samples=200,
        n_field_lineups=20,
        seed=7,
        max_per_team=2,
        dynamic_team_cap=False,
    )
    rec = optimize_lineup(samps, fields, curve, cfg=cfg)
    pid_to_boost = {f.player_id: f.card_boost for f in fields}
    picked = [pid_to_boost[p] for p in rec.player_ids]
    # The unconstrained optimum stacks the high-boost cards.
    assert sum(picked) >= 13.0, f"sanity: uncapped should load up; got picks {picked}"


def test_optimize_lineup_boost_sum_cap_drops_high_boost() -> None:
    """With BOOST_SUM_CAP=9 the optimizer cannot ship the all-3.0 lineup."""
    boosts = [3.0, 3.0, 3.0, 2.5, 2.0, 1.0, 3.0, 3.0, 3.0, 2.5, 2.0, 1.0]
    samps, fields = _spec_pair(boost_grid=boosts)
    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(
        top_n_filter=12,
        n_samples=200,
        n_field_lineups=20,
        seed=7,
        max_per_team=2,
        dynamic_team_cap=False,
        boost_sum_cap=9.0,
    )
    rec = optimize_lineup(samps, fields, curve, cfg=cfg)
    pid_to_boost = {f.player_id: f.card_boost for f in fields}
    picked = [pid_to_boost[p] for p in rec.player_ids]
    assert sum(picked) <= 9.0 + 1e-9, f"cap not honoured; picks sum to {sum(picked)}"


def test_optimize_lineup_max_single_boost_blocks_3p0_tier() -> None:
    """With MAX_SINGLE_BOOST=2.5 no 3.0 card lands in the lineup."""
    boosts = [3.0, 3.0, 3.0, 2.5, 2.0, 1.0, 3.0, 3.0, 3.0, 2.5, 2.0, 1.0]
    samps, fields = _spec_pair(boost_grid=boosts)
    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(
        top_n_filter=12,
        n_samples=200,
        n_field_lineups=20,
        seed=7,
        max_per_team=2,
        dynamic_team_cap=False,
        max_single_boost=2.5,
    )
    rec = optimize_lineup(samps, fields, curve, cfg=cfg)
    pid_to_boost = {f.player_id: f.card_boost for f in fields}
    picked = [pid_to_boost[p] for p in rec.player_ids]
    assert max(picked) <= 2.5 + 1e-9, f"per-pick cap not honoured; picks {picked}"


def test_optimize_lineup_relaxes_when_jointly_infeasible() -> None:
    """When the boost caps starve the pool (every player has boost > 2.5),
    the optimizer warns and relaxes -- it must NEVER forfeit a slate."""
    boosts = [3.0] * 12  # entire pool is 3.0 boost
    samps, fields = _spec_pair(boost_grid=boosts)
    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(
        top_n_filter=12,
        n_samples=200,
        n_field_lineups=20,
        seed=7,
        max_per_team=2,
        dynamic_team_cap=False,
        boost_sum_cap=7.5,
        max_single_boost=2.0,
    )
    rec = optimize_lineup(samps, fields, curve, cfg=cfg)
    assert len(rec.player_ids) == 5, "optimizer forfeited the slate"
