"""Tiny L2-regularized linear regression (stdlib only; no numpy/sklearn)."""

from __future__ import annotations

from dataclasses import dataclass


def _mat_vec(a: list[list[float]], x: list[float]) -> list[float]:
    return [sum(aij * xj for aij, xj in zip(ai, x, strict=True)) for ai in a]


def _solve_linear(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting for a square system."""

    n = len(b)
    if n == 0:
        return []
    if any(len(row) != n for row in a) or len(a) != n:
        raise ValueError("a must be square and match b")
    m = [row[:] + [bi] for row, bi in zip(a, b, strict=True)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            # Singular / near-singular: leave a zero solution component.
            continue
        if pivot != col:
            m[col], m[pivot] = m[pivot], m[col]
        div = m[col][col]
        for j in range(col, n + 1):
            m[col][j] /= div
        for row in range(n):
            if row == col:
                continue
            factor = m[row][col]
            if factor == 0.0:
                continue
            for j in range(col, n + 1):
                m[row][j] -= factor * m[col][j]
    return [m[i][n] for i in range(n)]


@dataclass
class RidgeRegressor:
    """Ordinary ridge: minimize ||Xw - y||^2 + alpha * ||w[1:]||^2 (no intercept pen)."""

    alpha: float = 1.0
    coefficients: list[float] | None = None

    def fit(self, x: list[list[float]], y: list[float]) -> RidgeRegressor:
        if len(x) != len(y):
            raise ValueError("x and y length mismatch")
        if not x:
            self.coefficients = []
            return self
        n_features = len(x[0])
        if any(len(row) != n_features for row in x):
            raise ValueError("ragged feature rows")
        # XtX and Xt y
        xtx = [[0.0] * n_features for _ in range(n_features)]
        xty = [0.0] * n_features
        for row, yi in zip(x, y, strict=True):
            for i in range(n_features):
                xty[i] += row[i] * yi
                xi = row[i]
                for j in range(n_features):
                    xtx[i][j] += xi * row[j]
        # Penalize all but intercept (index 0) when present.
        for i in range(1, n_features):
            xtx[i][i] += self.alpha
        self.coefficients = _solve_linear(xtx, xty)
        return self

    def predict(self, x: list[list[float]]) -> list[float]:
        if self.coefficients is None:
            raise RuntimeError("RidgeRegressor.fit must be called before predict")
        if not self.coefficients:
            return [0.0] * len(x)
        return [sum(c * v for c, v in zip(self.coefficients, row, strict=True)) for row in x]
