"""Tier 1 lineup anchor floor (D57): the optimizer must field >= min_anchors
confirmed-minutes anchors, and must never forfeit when anchors are scarce."""

from __future__ import annotations

import numpy as np

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.sample import PlayerSamplingSpec

CURVE = default_curve_for_regime("top_20")
MU = float(np.log(3.0 + 2.0))  # pred_real_score 3.0 at K=2 (log(pred + K))


def _pool(n_darts: int, n_anchors: int) -> tuple[list, list, set[int]]:
    """Darts and anchors with IDENTICAL real_score distributions; darts carry a
    big card_boost (3.0) and anchors a small one (0.5). With equal real_score
    the boost-3 darts strictly dominate on (slot + boost) x value, so the
    unconstrained optimum is all darts -- exactly the 2026-06-01 shape."""
    samps: list[PlayerSamplingSpec] = []
    fields: list[FieldPlayerSpec] = []
    anchor_ids: set[int] = set()
    pid = 1
    for _ in range(n_darts):
        samps.append(
            PlayerSamplingSpec(pid, "LVA", "NYL", mu=MU, sigma=0.3, boost=3.0, is_anchor=False)
        )
        fields.append(FieldPlayerSpec(player_id=pid, pred_real_score=3.0, card_boost=3.0))
        pid += 1
    for _ in range(n_anchors):
        samps.append(
            PlayerSamplingSpec(pid, "LVA", "NYL", mu=MU, sigma=0.3, boost=0.5, is_anchor=True)
        )
        fields.append(FieldPlayerSpec(player_id=pid, pred_real_score=3.0, card_boost=0.5))
        anchor_ids.add(pid)
        pid += 1
    return samps, fields, anchor_ids


def _cfg(min_anchors: int) -> OptimizeConfig:
    # Team cap fully disabled (max_per_team=5, dynamic off) to isolate the
    # anchor floor; small sample counts keep the test fast and deterministic.
    return OptimizeConfig(
        top_n_filter=8,
        n_samples=400,
        n_field_lineups=60,
        max_per_team=5,
        dynamic_team_cap=False,
        min_anchors=min_anchors,
    )


def test_anchor_floor_binds() -> None:
    samps, fields, anchor_ids = _pool(n_darts=5, n_anchors=3)
    off = optimize_lineup(samps, fields, CURVE, cfg=_cfg(0))
    on = optimize_lineup(samps, fields, CURVE, cfg=_cfg(2))
    n_off = sum(p in anchor_ids for p in off.player_ids)
    n_on = sum(p in anchor_ids for p in on.player_ids)
    assert n_off < 2  # unconstrained: boost-3 darts dominate
    assert n_on >= 2  # the floor forces the floor+ceiling barbell
    assert len(on.player_ids) == 5


def test_anchor_floor_never_forfeits_without_anchors() -> None:
    # min_anchors=2 but the pool has ZERO anchors -> clamp to available (0) and
    # still ship a full 5-player lineup rather than forfeit (the D50 lesson).
    samps, fields, _ = _pool(n_darts=6, n_anchors=0)
    rec = optimize_lineup(samps, fields, CURVE, cfg=_cfg(2))
    assert len(rec.player_ids) == 5
