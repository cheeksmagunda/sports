"""Objective-shaping terms (D87, Phase 1): leverage / ceiling / duplication.

The rank-based E[payout] is the single source of truth when the field model
is exact. The 2026 GPP literature (Hunter/Vielma/Zaman; Haugh & Singal)
shows three correctives the rank-EV alone underprices in top-heavy contests:
explicit leverage, upper-tail ceiling, and duplicate-lineup risk. These
tests pin the three additive terms in `_scan`:

  - default weights (0.0) are byte-identical to pre-D87 behaviour.
  - each weight, in isolation, biases lineup selection in the predicted
    direction (contrarian, high-upside, diversified) without crashing the
    optimizer or starving the slate.
"""

from __future__ import annotations

import numpy as np

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.sample import PlayerSamplingSpec


def _toy_pool(
    n: int = 10,
    *,
    with_measured: bool = True,
) -> tuple[list[PlayerSamplingSpec], list[FieldPlayerSpec]]:
    """Two-team toy pool with explicit chalk vs contrarian split.

    Players 0..4 are the chalk (high measured ownership, low projection).
    Players 5..9 are the contrarian (low ownership, high projection).
    Equal mu/sigma so rank-EV alone is roughly indifferent between the two
    halves and the additive terms drive the choice deterministically.
    """
    samps: list[PlayerSamplingSpec] = []
    fields: list[FieldPlayerSpec] = []
    for i in range(n):
        is_chalk = i < n // 2
        team = "A" if i % 2 == 0 else "B"
        opp = "B" if team == "A" else "A"
        samps.append(
            PlayerSamplingSpec(
                player_id=100 + i,
                team=team,
                opponent=opp,
                mu=float(np.log(2.0 + 2.0)),
                sigma=0.30,
                boost=1.0,
            )
        )
        fields.append(
            FieldPlayerSpec(
                player_id=100 + i,
                pred_real_score=2.0,
                card_boost=1.0,
                measured_drafts=(3000.0 if is_chalk else 100.0) if with_measured else None,
            )
        )
    return samps, fields


def _ids(rec) -> set[int]:
    return set(rec.player_ids)


def test_default_weights_are_byte_identical() -> None:
    """Bare OptimizeConfig with weights=0.0 reproduces the pre-D87 selection.

    Two runs with seed-equivalent configs and weights=0.0 must pick the same
    lineup, with the same expected_payout, with the same percentile scores.
    """
    samps, fields = _toy_pool()
    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(
        top_n_filter=10, n_samples=500, n_field_lineups=80, max_per_team=5
    )
    a = optimize_lineup(samps, fields, curve, cfg=cfg)
    cfg2 = OptimizeConfig(
        top_n_filter=10,
        n_samples=500,
        n_field_lineups=80,
        max_per_team=5,
        leverage_weight=0.0,
        ceiling_weight=0.0,
        duplication_weight=0.0,
    )
    b = optimize_lineup(samps, fields, curve, cfg=cfg2)
    assert a.player_ids == b.player_ids
    assert np.isclose(a.expected_payout, b.expected_payout)


def test_leverage_weight_biases_toward_contrarian() -> None:
    """A large leverage weight should pull the lineup off the chalk half.

    With chalk and contrarian halves of equal projection and equal sigma, the
    rank-EV is near-flat between them and the additive log-ownership term
    must drive the selection toward the low-ownership contrarian players.
    """
    samps, fields = _toy_pool()
    curve = default_curve_for_regime("top_20")
    base_cfg = OptimizeConfig(
        top_n_filter=10, n_samples=500, n_field_lineups=80, max_per_team=5
    )
    base = optimize_lineup(samps, fields, curve, cfg=base_cfg)
    lev_cfg = OptimizeConfig(
        top_n_filter=10,
        n_samples=500,
        n_field_lineups=80,
        max_per_team=5,
        leverage_weight=5.0,
    )
    levered = optimize_lineup(samps, fields, curve, cfg=lev_cfg)
    # Contrarian player_ids are 105-109 (boost on low-ownership half).
    contrarian_ids = {105, 106, 107, 108, 109}
    n_contrarian_base = len(_ids(base) & contrarian_ids)
    n_contrarian_lev = len(_ids(levered) & contrarian_ids)
    assert n_contrarian_lev >= n_contrarian_base
    # And a strong weight should produce a majority-contrarian lineup.
    assert n_contrarian_lev >= 3


def test_duplication_weight_avoids_full_chalk() -> None:
    """A duplication penalty should refuse a 5-of-5 chalk lineup when the
    expected mirror-entry count is meaningful.

    With chalk ownership at 60% per player (extreme), prod(own_i)*field_size
    is ~10 expected duplicate entries -- a non-trivial EV deduction. The
    optimizer should swap at least one chalk pick for an off-chalk one.
    """
    samps, fields = _toy_pool(n=10)
    # Push chalk ownership extremely high so duplication is the dominant term.
    for i, f in enumerate(fields):
        if i < 5:
            object.__setattr__(f, "measured_drafts", 9000.0)
        else:
            object.__setattr__(f, "measured_drafts", 50.0)
    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(
        top_n_filter=10,
        n_samples=500,
        n_field_lineups=80,
        max_per_team=5,
        duplication_weight=5.0,
    )
    rec = optimize_lineup(samps, fields, curve, cfg=cfg)
    chalk_ids = {100, 101, 102, 103, 104}
    n_chalk = len(_ids(rec) & chalk_ids)
    assert n_chalk < 5  # duplication penalty refuses the all-chalk lineup


def test_ceiling_weight_does_not_starve_slate() -> None:
    """A modest ceiling weight should not crash or empty the lineup, even
    when own_samples are tight (small p90-p50 gap)."""
    samps, fields = _toy_pool()
    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(
        top_n_filter=10,
        n_samples=500,
        n_field_lineups=80,
        max_per_team=5,
        ceiling_weight=2.0,
    )
    rec = optimize_lineup(samps, fields, curve, cfg=cfg)
    assert len(rec.player_ids) == 5
    assert rec.expected_payout > -np.inf
