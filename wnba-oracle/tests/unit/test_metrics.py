"""Metrics tests: CRPS, coverage, ECE."""

from __future__ import annotations

import numpy as np

from wnba_oracle.eval.metrics import coverage, crps_from_quantiles, quantile_loss


def test_quantile_loss_zero_when_perfect() -> None:
    y = np.array([1.0, 2.0, 3.0])
    assert quantile_loss(y, y, 0.5) == 0.0


def test_crps_from_perfect_quantiles_is_zero() -> None:
    y = np.array([1.0, 2.0, 3.0])
    assert crps_from_quantiles(y, y, y, y) == 0.0


def test_coverage_inside_band() -> None:
    y = np.array([1.0, 2.0, 3.0])
    lo = np.array([0.5, 1.5, 2.5])
    hi = np.array([1.5, 2.5, 3.5])
    assert coverage(y, lo, hi) == 1.0
    assert coverage(y, lo + 5, hi + 5) == 0.0
