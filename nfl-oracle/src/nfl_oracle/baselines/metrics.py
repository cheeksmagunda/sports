"""Honest scalar metrics for Real value baselines (stdlib only)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RegressionMetrics:
    n: int
    mae: float | None
    rmse: float | None
    bias: float | None
    actual_mean: float | None
    pred_mean: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def regression_metrics(actual: Sequence[float], predicted: Sequence[float]) -> RegressionMetrics:
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same length")
    n = len(actual)
    if n == 0:
        return RegressionMetrics(
            n=0,
            mae=None,
            rmse=None,
            bias=None,
            actual_mean=None,
            pred_mean=None,
        )
    abs_err = 0.0
    sq_err = 0.0
    signed = 0.0
    actual_sum = 0.0
    pred_sum = 0.0
    for y, yhat in zip(actual, predicted, strict=True):
        err = yhat - y
        abs_err += abs(err)
        sq_err += err * err
        signed += err
        actual_sum += y
        pred_sum += yhat
    return RegressionMetrics(
        n=n,
        mae=abs_err / n,
        rmse=math.sqrt(sq_err / n),
        bias=signed / n,
        actual_mean=actual_sum / n,
        pred_mean=pred_sum / n,
    )
