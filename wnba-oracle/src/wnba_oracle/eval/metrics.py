"""Calibration-first metrics: CRPS, reliability, ECE, quantile loss.

CRPS is the headline metric we publish in eval/. MAE and RMSE remain for
continuity with MLB Oracle but are not promotion gates.
"""

from __future__ import annotations

import numpy as np


def quantile_loss(y_true: np.ndarray, q_pred: np.ndarray, alpha: float) -> float:
    """Pinball loss at quantile alpha."""
    e = y_true - q_pred
    return float(np.mean(np.where(e >= 0, alpha * e, (alpha - 1) * e)))


def crps_from_quantiles(
    y_true: np.ndarray,
    q_lo: np.ndarray,
    q_mid: np.ndarray,
    q_hi: np.ndarray,
    alphas: tuple[float, float, float] = (0.1, 0.5, 0.9),
) -> float:
    """Approximate CRPS as a weighted sum of pinball losses at three quantiles.
    Standard 3-point quadrature; matches the LightGBM quantile-head training
    objective and is consistent with the calibration pipeline.
    """
    a_lo, a_mid, a_hi = alphas
    return (
        quantile_loss(y_true, q_lo, a_lo)
        + quantile_loss(y_true, q_mid, a_mid)
        + quantile_loss(y_true, q_hi, a_hi)
    ) / 3.0


def coverage(y_true: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    """Empirical fraction of `y_true` inside [lo, hi]."""
    inside = (y_true >= lo) & (y_true <= hi)
    return float(np.mean(inside))


def reliability_bins(
    y_true: np.ndarray,
    q: np.ndarray,
    quantile_level: float,
    n_bins: int = 10,
) -> dict[str, list[float]]:
    """For a single quantile prediction, bin by predicted value and compute
    empirical-vs-nominal coverage in each bin. Useful for the reliability
    diagram in eval/.
    """
    edges = np.quantile(q, np.linspace(0.0, 1.0, n_bins + 1))
    bin_ids = np.clip(np.searchsorted(edges[1:-1], q), 0, n_bins - 1)
    out: dict[str, list[float]] = {
        "bin_mean_pred": [],
        "bin_emp_cov": [],
        "bin_n": [],
    }
    for b in range(n_bins):
        mask = bin_ids == b
        if not mask.any():
            continue
        out["bin_mean_pred"].append(float(np.mean(q[mask])))
        # For a single quantile, "coverage" is the fraction with y <= q.
        out["bin_emp_cov"].append(float(np.mean(y_true[mask] <= q[mask])))
        out["bin_n"].append(int(mask.sum()))
    out["nominal"] = [quantile_level] * len(out["bin_mean_pred"])
    return out


def ece_from_quantile(
    y_true: np.ndarray, q: np.ndarray, quantile_level: float, n_bins: int = 10
) -> float:
    """Expected calibration error for a single quantile prediction."""
    bins = reliability_bins(y_true, q, quantile_level, n_bins=n_bins)
    if not bins["bin_mean_pred"]:
        return 0.0
    total = sum(bins["bin_n"])
    err = 0.0
    for n, emp in zip(bins["bin_n"], bins["bin_emp_cov"], strict=True):
        err += (n / total) * abs(emp - quantile_level)
    return float(err)
