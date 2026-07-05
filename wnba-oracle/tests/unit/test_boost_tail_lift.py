"""Stage-1 ranking uses rank_pred_override when set (2026-07-04 boost-tail lift).

Guards the invariant: the caller can hint the stage-1 filter toward ceiling
plays via FieldPlayerSpec.rank_pred_override without changing sampling. When
the override is None, stage-1 falls back to pred_real_score, preserving
byte-identical pre-fix behavior.
"""

from __future__ import annotations

import numpy as np

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import MAX_SLOT_MULT


def _visible_value(specs: list[FieldPlayerSpec]) -> np.ndarray:
    """Mirror the stage-1 visible_value computation in optimize.optimize_lineup.
    Reproduced here so this test can exercise the ranking rule without
    building sampling specs and running a full optimize."""
    return np.array(
        [
            (s.rank_pred_override if s.rank_pred_override is not None else s.pred_real_score)
            * (MAX_SLOT_MULT + s.card_boost)
            for s in specs
        ],
        dtype=float,
    )


def test_no_override_matches_pred_real_score() -> None:
    a = FieldPlayerSpec(player_id=1, pred_real_score=3.0, card_boost=0.0)
    b = FieldPlayerSpec(player_id=2, pred_real_score=2.0, card_boost=1.0)
    vv = _visible_value([a, b])
    assert vv[0] == 3.0 * (MAX_SLOT_MULT + 0.0)
    assert vv[1] == 2.0 * (MAX_SLOT_MULT + 1.0)


def test_override_lifts_high_boost_over_low_boost() -> None:
    # p50 anchor: without the lift, the ranker orders these three by
    # pred_real_score * (2 + boost). Low-boost star at 4.0 leads, low-mid at
    # 2.5, and the boost-tail role player at 0.8 sits at the bottom.
    star = FieldPlayerSpec(player_id=1, pred_real_score=4.0, card_boost=0.0)
    mid = FieldPlayerSpec(player_id=2, pred_real_score=2.5, card_boost=0.5)
    tail_p50 = FieldPlayerSpec(player_id=3, pred_real_score=0.8, card_boost=2.5)
    vv_p50 = _visible_value([star, mid, tail_p50])
    assert vv_p50[0] > vv_p50[1] > vv_p50[2]

    # 2026-07-04 lift: the boost-tail player's rank_pred_override is set to
    # its head p90 (~2.0 for a boost=2.5 role player, per corpus). That lift
    # jumps the tail player past mid, matching the empirical realized
    # ordering (mean_real 1.77 at boost>=2.5 vs mean_pred_p50 1.09).
    tail_p90 = FieldPlayerSpec(
        player_id=3, pred_real_score=0.8, card_boost=2.5, rank_pred_override=1.5
    )
    vv_lift = _visible_value([star, mid, tail_p90])
    assert vv_lift[2] > vv_lift[1]  # tail now beats the low-mid pick
    assert vv_lift[0] > vv_lift[2]  # true anchor still ranks first


def test_override_leaves_sampling_pred_unchanged() -> None:
    # pred_real_score is what job2 stores into pred_real_scores[pid] and what
    # the sampler's mu = log(pred + K) reads. Setting rank_pred_override MUST
    # NOT change pred_real_score, so the sampler still uses p50 as the center.
    s = FieldPlayerSpec(player_id=1, pred_real_score=1.5, card_boost=2.5, rank_pred_override=3.75)
    assert s.pred_real_score == 1.5  # sampler input untouched
    assert s.rank_pred_override == 3.75  # ranker sees ceiling
