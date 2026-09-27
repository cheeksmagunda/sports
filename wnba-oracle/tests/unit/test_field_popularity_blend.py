"""Field-ownership model: popularity-blend path (W2 / #453)."""

from __future__ import annotations

import numpy as np

from wnba_oracle.picker.field import FieldPlayerSpec, project_ownership


def _spec(
    pid: int,
    pred: float,
    boost: float,
    drafts: float | None = None,
    popularity: float | None = None,
    rank_pred_override: float | None = None,
) -> FieldPlayerSpec:
    return FieldPlayerSpec(
        player_id=pid,
        pred_real_score=pred,
        card_boost=boost,
        measured_drafts=drafts,
        popularity_score=popularity,
        rank_pred_override=rank_pred_override,
    )


def test_no_popularity_is_byte_identical_to_legacy() -> None:
    specs = [_spec(i, pred=2.0 + 0.1 * i, boost=1.0 + 0.05 * i) for i in range(6)]
    own = project_ownership(specs)
    assert np.isclose(own.sum(), 1.0)
    raw = np.array([s.pred_real_score * (1.0 + s.card_boost) for s in specs])
    raw = raw - raw.max()
    base = np.exp(raw / 6.0)
    expected = base / base.sum()
    assert np.allclose(own, expected)


def test_popularity_raises_star_ownership() -> None:
    specs = [
        _spec(1, pred=2.0, boost=1.0, popularity=5000.0),
        _spec(2, pred=2.0, boost=1.0, popularity=1000.0),
        _spec(3, pred=2.0, boost=1.0, popularity=2500.0),
        _spec(4, pred=2.0, boost=1.0, popularity=2000.0),
        _spec(5, pred=2.0, boost=1.0, popularity=1500.0),
    ]
    own = project_ownership(specs)
    assert np.isclose(own.sum(), 1.0)
    assert own[0] > own[2] > own[1]


def test_popularity_shifts_ownership_away_from_model_mirror() -> None:
    pop = [
        _spec(1, pred=3.0, boost=2.0, popularity=1000.0),
        _spec(2, pred=2.0, boost=1.0, popularity=2000.0),
        _spec(3, pred=1.5, boost=0.5, popularity=5000.0),
        _spec(4, pred=2.5, boost=1.5, popularity=2500.0),
        _spec(5, pred=2.0, boost=1.0, popularity=3000.0),
    ]
    no = [
        _spec(1, pred=3.0, boost=2.0),
        _spec(2, pred=2.0, boost=1.0),
        _spec(3, pred=1.5, boost=0.5),
        _spec(4, pred=2.5, boost=1.5),
        _spec(5, pred=2.0, boost=1.0),
    ]
    own_pop = project_ownership(pop)
    own_no = project_ownership(no)
    assert own_pop[2] > own_no[2]
    assert own_pop[0] < own_no[0]


def test_popularity_blend_zero_is_model_only() -> None:
    specs = [
        _spec(1, pred=3.0, boost=2.0, popularity=1000.0),
        _spec(2, pred=2.0, boost=1.0, popularity=5000.0),
        _spec(3, pred=1.5, boost=0.5, popularity=3000.0),
        _spec(4, pred=2.5, boost=1.5, popularity=2000.0),
        _spec(5, pred=2.0, boost=1.0, popularity=4000.0),
    ]
    no = [
        _spec(1, pred=3.0, boost=2.0),
        _spec(2, pred=2.0, boost=1.0),
        _spec(3, pred=1.5, boost=0.5),
        _spec(4, pred=2.5, boost=1.5),
        _spec(5, pred=2.0, boost=1.0),
    ]
    assert np.allclose(project_ownership(specs, popularity_blend=0.0), project_ownership(no))


def test_popularity_blend_one_is_popularity_dominated() -> None:
    specs = [
        _spec(1, pred=3.0, boost=2.0, popularity=100.0),
        _spec(2, pred=1.0, boost=0.5, popularity=5000.0),
        _spec(3, pred=2.0, boost=1.0, popularity=3000.0),
        _spec(4, pred=2.5, boost=1.5, popularity=2000.0),
        _spec(5, pred=1.5, boost=0.8, popularity=4000.0),
    ]
    own = project_ownership(specs, popularity_blend=1.0)
    assert np.isclose(own.sum(), 1.0)
    assert own[1] == own.max()
    assert own[0] == own.min()


def test_measured_drafts_still_dominate_with_popularity() -> None:
    specs = [
        _spec(1, pred=1.0, boost=1.0, drafts=5000, popularity=100.0),
        _spec(2, pred=3.0, boost=2.0, drafts=100, popularity=5000.0),
        _spec(3, pred=2.0, boost=1.0, drafts=2000, popularity=3000.0),
        _spec(4, pred=2.0, boost=1.0, drafts=1500, popularity=2000.0),
        _spec(5, pred=2.0, boost=1.0, drafts=1000, popularity=4000.0),
    ]
    own = project_ownership(specs)
    counts = np.array([5000, 100, 2000, 1500, 1000], dtype=float)
    assert np.allclose(own, counts / counts.sum())


def test_partial_popularity_scores_fall_back_per_player() -> None:
    specs = [
        _spec(1, pred=2.0, boost=1.0, popularity=5000.0),
        _spec(2, pred=2.0, boost=1.0, popularity=None),
        _spec(3, pred=2.0, boost=1.0, popularity=2500.0),
        _spec(4, pred=2.0, boost=1.0, popularity=None),
        _spec(5, pred=2.0, boost=1.0, popularity=1000.0),
    ]
    own = project_ownership(specs)
    assert np.isclose(own.sum(), 1.0)
    assert np.all(own > 0.0)
    assert own[0] > own[4]


def test_rank_pred_override_raises_chalk_ownership_vs_post_contrarian() -> None:
    """Post-contrarian sampler scores must not understate chalk ownership."""
    without = [
        _spec(1, pred=2.0, boost=1.0),
        _spec(2, pred=2.0, boost=1.0),
        _spec(3, pred=1.5, boost=0.5),
        _spec(4, pred=1.5, boost=0.5),
        _spec(5, pred=1.5, boost=0.5),
    ]
    with_override = [
        _spec(1, pred=2.0, boost=1.0, rank_pred_override=5.0),
        _spec(2, pred=2.0, boost=1.0, rank_pred_override=2.0),
        _spec(3, pred=1.5, boost=0.5, rank_pred_override=1.5),
        _spec(4, pred=1.5, boost=0.5, rank_pred_override=1.5),
        _spec(5, pred=1.5, boost=0.5, rank_pred_override=1.5),
    ]
    own_legacy = project_ownership(without)
    own_visible = project_ownership(with_override)
    assert np.isclose(own_legacy[0], own_legacy[1])
    assert own_visible[0] > own_visible[1]
    assert own_visible[0] > own_legacy[0]
