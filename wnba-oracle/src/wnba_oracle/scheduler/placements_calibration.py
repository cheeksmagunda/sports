"""Pure calibration math for the placement feedback loop: DB-free,
unit-testable. Extracted from placements.py.

PlacementRow derives finish_percentile/roi from a recorded outcome;
compute_pit_value/pit_histogram/chi2_uniformity_pvalue diagnose whether
the finish-percentile forecast is calibrated; ownership_log_loss_by_decile
localizes miscalibration in the field-ownership model. See placements.py's
module docstring for how these feed summarize_placements.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PlacementRow:
    slate_date: str
    contest_id: int
    entry_rank: int | None
    entry_count: int | None
    entry_score: float | None
    payout_cents: int | None
    entry_fee_cents: int | None

    @property
    def finish_percentile(self) -> float | None:
        if self.entry_rank is None or not self.entry_count:
            return None
        if self.entry_count <= 0:
            return None
        return float(self.entry_rank) / float(self.entry_count)

    @property
    def roi(self) -> float | None:
        if self.payout_cents is None or self.entry_fee_cents is None or self.entry_fee_cents <= 0:
            return None
        return float(self.payout_cents - self.entry_fee_cents) / float(self.entry_fee_cents)


def compute_pit_value(
    finish_percentile: float,
    predicted_cdf: dict[float, float] | None,
) -> float | None:
    """Probability-Integral Transform on the predicted finish CDF.

    `predicted_cdf` is {percentile_threshold: cumulative_probability} (e.g.
    {0.05: 0.10, 0.20: 0.30, 0.50: 0.60}). If the predicted distribution is
    calibrated, the PIT values over many slates are uniformly distributed
    on [0, 1]. Skew toward 0 / 1 signals bias; U-shape signals
    over-confidence (under-dispersion); dome shape signals over-dispersion.

    Returns None if cdf is missing or empty.
    """
    if predicted_cdf is None or not predicted_cdf:
        return None
    # Find the smallest threshold >= finish_percentile.
    items = sorted((float(k), float(v)) for k, v in predicted_cdf.items())
    for threshold, cum_prob in items:
        if finish_percentile <= threshold:
            return cum_prob
    # finish_percentile is past the worst tracked threshold -> at the upper
    # tail of the CDF (we finished worse than the predicted 50th percentile,
    # etc.). Clip at the last cumulative probability.
    return items[-1][1]


def pit_histogram(pit_values: list[float], n_bins: int = 10) -> list[int]:
    """Bin PIT values into `n_bins` equal-width bins on [0, 1]. Returns
    integer counts per bin. A perfectly calibrated forecaster produces a
    flat histogram; deviations diagnose simulator dispersion."""
    counts = [0] * n_bins
    for v in pit_values:
        if v is None:
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if not (0.0 <= x <= 1.0):
            continue
        idx = min(int(x * n_bins), n_bins - 1)
        counts[idx] += 1
    return counts


def chi2_uniformity_pvalue(counts: list[int]) -> float | None:
    """Pearson chi-square uniformity test on the PIT histogram. Returns the
    p-value; small p means the histogram is unlikely uniform (forecast not
    calibrated). Returns None when total < 30 (test underpowered).
    """
    total = sum(counts)
    if total < 30:
        return None
    n_bins = len(counts)
    expected = total / float(n_bins)
    chi2 = sum((c - expected) ** 2 / expected for c in counts)
    # Survival function of chi2 with (n_bins - 1) df. Use a Wilson-Hilferty
    # approximation to avoid pulling scipy for a single tail-area lookup.
    df = n_bins - 1
    if df <= 0:
        return None
    a = chi2 / df
    z = ((a ** (1 / 3)) - (1 - 2 / (9 * df))) / ((2 / (9 * df)) ** 0.5)
    # Standard normal tail. Abramowitz-Stegun 26.2.17 approximation.
    return _stdnorm_sf(z)


def _stdnorm_sf(z: float) -> float:
    # 1 - Phi(z) via Abramowitz-Stegun 26.2.17. Sufficient accuracy
    # (~1e-7) for our calibration p-values; avoids the scipy dep.
    if z < 0:
        return 1.0 - _stdnorm_sf(-z)
    t = 1.0 / (1.0 + 0.2316419 * z)
    p = (
        0.319381530 * t
        - 0.356563782 * t**2
        + 1.781477937 * t**3
        - 1.821255978 * t**4
        + 1.330274429 * t**5
    )
    pdf = 0.39894228 * pow(2.71828182845905, -0.5 * z * z)
    return pdf * p


def ownership_log_loss_by_decile(
    projected: dict[int, float], actual: dict[int, float]
) -> list[tuple[float, float, int]]:
    """Per-decile binary cross-entropy on projected vs actual ownership.

    Players are bucketed by `projected` into 10 deciles. Within each bucket
    LL = -mean(y log p + (1-y) log(1-p)) over the players in the bucket,
    treating actual ownership as the Bernoulli probability target.

    Returns [(bucket_upper, log_loss, n_players), ...] for the 10 deciles
    (0.0-0.1, 0.1-0.2, ..., 0.9-1.0). A bucket with far-higher log-loss
    than its neighbours localizes the miscalibration regime (e.g. the
    20-30% projected bucket is being systematically underowned).
    """
    if not projected or not actual:
        return []
    common = set(projected) & set(actual)
    if not common:
        return []
    eps = 1e-9
    buckets: dict[int, list[tuple[float, float]]] = {i: [] for i in range(10)}
    for pid in common:
        p = max(eps, min(1.0 - eps, float(projected[pid])))
        y = max(0.0, min(1.0, float(actual[pid])))
        decile = min(int(p * 10), 9)
        buckets[decile].append((p, y))
    out: list[tuple[float, float, int]] = []
    for d in range(10):
        rows = buckets[d]
        if not rows:
            out.append(((d + 1) / 10.0, float("nan"), 0))
            continue
        ll = -sum(y * math.log(p) + (1 - y) * math.log(1 - p) for p, y in rows) / len(rows)
        out.append(((d + 1) / 10.0, ll, len(rows)))
    return out
