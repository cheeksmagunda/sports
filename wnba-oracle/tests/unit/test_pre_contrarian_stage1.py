"""Stage-1 pool ranks on pre-contrarian total draft value (#416).

Contrarian may reshape sampler means, but near-cutline chalk studs must
remain in ``top_n_filter`` when their pre-contrarian TV is highest.
"""

from __future__ import annotations

import numpy as np

from wnba_oracle.modeling.policy import ModelPolicy
from wnba_oracle.modeling.prediction import (
    PlayerPredictions,
    materialize_specs,
    stage1_rank_pred,
)
from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import MAX_SLOT_MULT, OptimizeConfig, _filter_pool, _StackContext
from wnba_oracle.picker.popularity import ContrarianConfig, apply_contrarian_adjustment
from wnba_oracle.picker.sample import PlayerSamplingSpec


def _visible_tv(spec: FieldPlayerSpec) -> float:
    rank = spec.rank_pred_override if spec.rank_pred_override is not None else spec.pred_real_score
    return float(rank) * (MAX_SLOT_MULT + float(spec.card_boost))


def _policy() -> ModelPolicy:
    return ModelPolicy(optimizer=OptimizeConfig())


def _empty_stack() -> _StackContext:
    return _StackContext(
        game_key_by_player={},
        metadata_quality="absent",
        slate_game_count=None,
        slate_team_count=0,
        preference=None,
    )


def test_stage1_rank_pred_floors_at_pre_contrarian() -> None:
    assert stage1_rank_pred(pre_contrarian=3.0) == 3.0
    assert stage1_rank_pred(pre_contrarian=3.0, boost_tail_rank=2.5) == 3.0
    assert stage1_rank_pred(pre_contrarian=3.0, boost_tail_rank=4.5) == 4.5


def test_materialize_keeps_pre_contrarian_rank_and_adjusted_sampler() -> None:
    pre = {101: 3.0, 102: 2.95, 103: 2.9}
    pop = {101: 4000.0, 102: 0.0, 103: 0.0}
    adjusted = apply_contrarian_adjustment(pre, pop, ContrarianConfig(strength=0.2))
    assert adjusted[101] < pre[101]

    preds = PlayerPredictions(
        pred_real_scores=dict(pre),
        rows_by_pid={
            pid: {"team": "AAA", "opponent": "BBB", "card_boost": 0.0, "name": f"P{pid}"}
            for pid in pre
        },
    )
    samps, fields, _proj = materialize_specs(
        adjusted,
        preds=preds,
        policy=_policy(),
        measured_drafts={},
        label_names={},
        K=2.0,
        volatility={},
    )
    by_pid = {f.player_id: f for f in fields}
    chalk = by_pid[101]
    assert chalk.pred_real_score == adjusted[101]
    assert chalk.rank_pred_override == pre[101]
    assert _visible_tv(chalk) > _visible_tv(by_pid[102]) > _visible_tv(by_pid[103])
    samp_by_pid = {s.player_id: s for s in samps}
    assert samp_by_pid[101].mu == float(np.log(max(adjusted[101] + 2.0, 1.0)))


def test_near_cutline_chalk_stays_in_top_n_when_contrarian_would_drop_it() -> None:
    """High-TV chalk exits top_n under adjusted ranking; pre-contrarian keeps it."""
    pre = {1: 3.0, 2: 2.95, 3: 2.9}
    pop = {1: 4000.0, 2: 0.0, 3: 0.0}
    adjusted = apply_contrarian_adjustment(pre, pop)

    # Legacy path: stage-1 sees contrarian-adjusted pred only.
    legacy_fields = [
        FieldPlayerSpec(player_id=pid, pred_real_score=adj, card_boost=0.0)
        for pid, adj in adjusted.items()
    ]
    # #416 path: rank on pre-contrarian; sampler still uses adjusted.
    tdv_fields = [
        FieldPlayerSpec(
            player_id=pid,
            pred_real_score=adj,
            card_boost=0.0,
            rank_pred_override=pre[pid],
        )
        for pid, adj in adjusted.items()
    ]
    samps = [
        PlayerSamplingSpec(
            player_id=pid,
            team="T",
            opponent="O",
            mu=0.0,
            sigma=0.2,
            boost=0.0,
        )
        for pid in pre
    ]
    cfg_top_n = 2
    stack = _empty_stack()
    legacy_pool = _filter_pool(
        samps, legacy_fields, cfg_top_n, MAX_SLOT_MULT, stack, coverage_aware=False
    )
    tdv_pool = _filter_pool(
        samps, tdv_fields, cfg_top_n, MAX_SLOT_MULT, stack, coverage_aware=False
    )
    legacy_ids = set(legacy_pool.player_ids)
    tdv_ids = set(tdv_pool.player_ids)

    assert 1 not in legacy_ids  # chalk dropped by popularity penalty
    assert 1 in tdv_ids  # chalk retained by pre-contrarian TV
    assert len(tdv_ids) == cfg_top_n


def test_boost_tail_lift_still_raises_stage1_above_pre_contrarian() -> None:
    pre = {7: 2.0}
    adjusted = {7: 1.9}
    preds = PlayerPredictions(
        pred_real_scores=dict(pre),
        rank_pred_by_pid={7: 3.5},
        rows_by_pid={7: {"team": "AAA", "opponent": "BBB", "card_boost": 2.5, "name": "Tail"}},
    )
    _samps, fields, _proj = materialize_specs(
        adjusted,
        preds=preds,
        policy=_policy(),
        measured_drafts={},
        label_names={},
        K=2.0,
        volatility={},
    )
    assert fields[0].pred_real_score == 1.9
    assert fields[0].rank_pred_override == 3.5
