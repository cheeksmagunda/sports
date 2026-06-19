"""#13a: vectorized expected_payout / payouts_for_ranks must be numerically
identical to the original per-sample Python loop. This is the safety proof for
the speedup -- no behavioral change, just numpy instead of a Python loop."""

from __future__ import annotations

import numpy as np
import pytest

from wnba_oracle.picker.payout import (
    PayoutCurve,
    default_curve_for_regime,
    expected_payout,
)


def _loop_payouts_for_ranks(curve: PayoutCurve, ranks, field_size: int):
    return np.array([curve.payout_for_rank(int(r), field_size) for r in ranks], dtype=float)


def _loop_expected_payout(own, field, curve, field_size):
    n_samples = field.shape[1]
    out = np.zeros(n_samples)
    for s in range(n_samples):
        rank = int(np.sum(field[:, s] > own[s]))
        out[s] = curve.payout_for_rank(rank, field_size)
    return float(out.mean())


@pytest.mark.parametrize("regime", ["top_1", "top_20", "top_50"])
def test_payouts_for_ranks_matches_scalar(regime: str) -> None:
    curve = default_curve_for_regime(regime)
    field_size = 501
    ranks = np.arange(0, field_size + 5)  # includes ranks past the field
    vec = curve.payouts_for_ranks(ranks, field_size)
    ref = _loop_payouts_for_ranks(curve, ranks, field_size)
    assert np.array_equal(vec, ref)


def test_payouts_for_ranks_edges() -> None:
    curve = default_curve_for_regime("top_20")
    assert np.array_equal(curve.payouts_for_ranks(np.array([0, 1, 2]), 0), np.zeros(3))
    # custom curve where cash_line exceeds the largest threshold (exercises the
    # loop's `best` fallback for pct above all thresholds but in the cash line)
    c = PayoutCurve(percentile_to_payout={0.1: 2.0}, regime="x", cash_line_percentile=0.5)
    ranks = np.array([5, 30, 49, 60])  # pct 0.05, 0.30, 0.49, 0.60 of field 100
    assert np.array_equal(c.payouts_for_ranks(ranks, 100), _loop_payouts_for_ranks(c, ranks, 100))


@pytest.mark.parametrize("regime", ["top_1", "top_20", "top_50"])
@pytest.mark.parametrize("seed", [0, 7, 42])
def test_expected_payout_matches_loop(regime: str, seed: int) -> None:
    rng = np.random.default_rng(seed)
    n_field, n_samples = 60, 400
    own = rng.normal(180, 30, size=n_samples)
    field = rng.normal(175, 28, size=(n_field, n_samples))
    curve = default_curve_for_regime(regime)
    vec = expected_payout(own, field, curve, field_size=n_field + 1)
    ref = _loop_expected_payout(own, field, curve, n_field + 1)
    assert vec == pytest.approx(ref, abs=1e-12)


def test_expected_payout_empty() -> None:
    curve = default_curve_for_regime("top_20")
    assert expected_payout(np.array([]), np.zeros((0, 0)), curve) == 0.0
