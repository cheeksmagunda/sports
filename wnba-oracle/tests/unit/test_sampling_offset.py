"""score_offset (K) calibration in the copula sampler (D52).

The offset is the K in log(real_score + K). It must (a) round-trip (be
subtracted after exp) and (b) control the implied real_score spread: at the
old K=10 a sigma=0.25 implied ~3x the observed real_score std and flattened
the skew; at K=2 the implied std matches reality and the skew is preserved.
"""

from __future__ import annotations

import numpy as np

from wnba_oracle.picker.sample import (
    CopulaConfig,
    PlayerSamplingSpec,
    sample_joint_real_scores,
)


def _spec(pred: float, K: float, sigma: float = 0.25) -> PlayerSamplingSpec:
    return PlayerSamplingSpec(
        player_id=1, team="AAA", opponent="BBB",
        mu=float(np.log(pred + K)), sigma=sigma, boost=1.0,
    )


def test_offset_roundtrips_to_pred_mean() -> None:
    pred = 2.5
    for K in (2.0, 10.0):
        s = sample_joint_real_scores(
            [_spec(pred, K)], 40000, CopulaConfig(seed=7, score_offset=K)
        )
        # E[exp(N(mu,s))] - K = (pred+K)*exp(s^2/2) - K, a slight upward bias.
        expected = (pred + K) * np.exp(0.25**2 / 2) - K
        assert abs(float(s.mean()) - expected) < 0.1


def test_smaller_offset_tightens_realized_spread() -> None:
    pred = 2.5
    s2 = sample_joint_real_scores([_spec(pred, 2.0)], 40000, CopulaConfig(seed=7, score_offset=2.0))
    s10 = sample_joint_real_scores([_spec(pred, 10.0)], 40000, CopulaConfig(seed=7, score_offset=10.0))
    std2, std10 = float(s2.std()), float(s10.std())
    # K=2 lands near the observed per-player std (~1.1); K=10 is ~3x too wide.
    assert 0.8 < std2 < 1.5
    assert std10 > 2.5
    assert std10 > 2 * std2
