"""Mondrian Conformalized Quantile Regression (CQR).

Pure-numpy implementation. The original plan was to use `mapie` 0.9's
MapieQuantileRegressor with a Mondrian helper; the dependency was dropped
during the post-build dep trim because nothing in the codebase imported
it. Re-add `mapie` to pyproject.toml when swapping this in.

Given calibration residuals split by `cohort` (G/F/C) and `condition`
(home/away, b2b/rested), we compute conformity scores and translate
them into a finite-sample-corrected band scaling factor per cell.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np


@dataclass
class MondrianCQR:
    target_coverage: float = 0.8
    # cell_residuals[(cohort, ...)] -> list[abs_residual]
    cell_residuals: dict[tuple[str, ...], list[float]] = field(default_factory=dict)
    cell_q: dict[tuple[str, ...], float] = field(default_factory=dict)

    def fit(
        self,
        y_true: np.ndarray,
        q_lo: np.ndarray,
        q_hi: np.ndarray,
        cell_keys: Sequence[tuple[str, ...]],
    ) -> None:
        """y_true, q_lo, q_hi are 1-D numpy arrays of length N.
        cell_keys is a length-N sequence of tuples identifying the
        Mondrian cell each calibration row belongs to.
        """
        n = len(y_true)
        if not (len(q_lo) == len(q_hi) == n == len(cell_keys)):
            raise ValueError("inputs must have matching length")
        # Conformity score: max(q_lo - y_true, y_true - q_hi) (CQR; Romano 2019).
        scores = np.maximum(q_lo - y_true, y_true - q_hi)
        for s, k in zip(scores.tolist(), cell_keys, strict=True):
            self.cell_residuals.setdefault(k, []).append(float(s))
        alpha = 1.0 - self.target_coverage
        for k, residuals in self.cell_residuals.items():
            m = len(residuals)
            # Finite-sample correction: ceil((m+1) * (1 - alpha)) / m quantile.
            rank = math.ceil((m + 1) * (1.0 - alpha))
            rank = max(1, min(rank, m))
            self.cell_q[k] = float(sorted(residuals)[rank - 1])

    def adjust(
        self, q_lo: np.ndarray, q_hi: np.ndarray, cell_keys: Sequence[tuple[str, ...]]
    ) -> tuple[np.ndarray, np.ndarray]:
        """Apply conformal correction to model quantiles."""
        out_lo = np.empty_like(q_lo, dtype=float)
        out_hi = np.empty_like(q_hi, dtype=float)
        global_q = (
            float(np.median(list(self.cell_q.values()))) if self.cell_q else 0.0
        )
        for i, k in enumerate(cell_keys):
            q = self.cell_q.get(k, global_q)
            out_lo[i] = float(q_lo[i]) - q
            out_hi[i] = float(q_hi[i]) + q
        return out_lo, out_hi
