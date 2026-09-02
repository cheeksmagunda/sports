"""Calibration helpers.

`PCHIPIsotonic` wraps scipy.interpolate.PchipInterpolator to give us a
monotone, smooth bijection from raw quantile predictions to calibrated
predictions on the training data CDF. Used post-LightGBM, pre-conformal.

`apply_jensen_correction` adds back the half-variance term when projecting
from log-scale to real-scale predictions (the multi-task heads operate in
log space to stabilize the long tail; the Jensen term unbiases the median
projection).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.interpolate import PchipInterpolator


@dataclass
class PCHIPIsotonic:
    """Monotone CDF interpolator for offline calibration analysis.

    Note: Calibrators are fitted for offline diagnostics/evaluation and are NOT
    consumed during production serving (serving_consumed=False).
    """

    x: np.ndarray | None = None
    y: np.ndarray | None = None
    serving_consumed: bool = False

    def fit(self, x_raw: np.ndarray, y_true: np.ndarray, n_knots: int = 20) -> None:
        if x_raw.size == 0:
            self.x = None
            self.y = None
            return
        # Sort by raw prediction; choose evenly spaced quantile knots.
        order = np.argsort(x_raw)
        xs = x_raw[order]
        ys = y_true[order]
        if xs.size <= n_knots:
            self.x = xs
            self.y = np.maximum.accumulate(ys)
            return
        idx = np.linspace(0, xs.size - 1, n_knots).astype(int)
        kx = xs[idx]
        ky = np.maximum.accumulate(ys[idx])
        # PCHIP requires strictly increasing x; bump duplicates.
        eps = 1e-9
        for i in range(1, kx.size):
            if kx[i] <= kx[i - 1]:
                kx[i] = kx[i - 1] + eps
        self.x = kx
        self.y = ky

    def transform(self, x: np.ndarray) -> np.ndarray:
        if self.x is None or self.y is None or self.x.size < 2:
            return x.astype(float)
        spline = PchipInterpolator(self.x, self.y, extrapolate=True)
        return np.asarray(spline(x), dtype=float)


def apply_jensen_correction(log_pred: np.ndarray, log_sigma: np.ndarray) -> np.ndarray:
    """E[exp(X)] = exp(mu + 0.5 * sigma^2). Cap sigma to avoid blow-ups in
    sparse-data tails."""
    capped_sigma = np.minimum(log_sigma, 1.0)
    return np.exp(log_pred + 0.5 * capped_sigma**2)
