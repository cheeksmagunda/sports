"""Payout-curve loader and per-lineup EV computation.

Real Sports' contest stats endpoint surfaces `info.rankDisplayInfos`
post-tip with the percentile-to-payout schedule. Pregame, the schedule is
null and we default to the top_20 regime per Part 1.2.

Payout regimes (Part 1.2):
- top_50  : linear above the cash line. Minimum variance subject to mean
            above the line.
- top_20  : convex above the line. Mild contrarianism.
- top_1   : sharply convex. Variance is asset.

The PayoutCurve class converts a percentile rank (0.0 = winner, 1.0 = last)
to a payout multiplier. EV of a lineup against a field is then:

    E[payout(rank(lineup_score, field_scores))]

computed by Monte Carlo over (joint samples of own lineup) X (sampled
field lineups).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
PAYOUT_ARCHIVE_DIR = REPO_ROOT / "data" / "contest_payouts"


@dataclass
class PayoutCurve:
    """percentile_to_payout maps top-percentile thresholds (e.g. 0.01, 0.05,
    0.10, 0.20, 0.50) to payout multipliers. Outside the cash line returns 0.
    """

    percentile_to_payout: dict[float, float] = field(default_factory=dict)
    regime: str = "top_20"
    cash_line_percentile: float = 0.5

    def payout_for_rank(self, rank: int, field_size: int) -> float:
        if field_size <= 0:
            return 0.0
        pct = float(rank) / float(field_size)
        if pct > self.cash_line_percentile:
            return 0.0
        # Step function over the percentile thresholds.
        best = 0.0
        for threshold, mult in sorted(self.percentile_to_payout.items()):
            if pct <= threshold:
                return float(mult)
            best = float(mult)
        return best


def default_curve_for_regime(regime: str) -> PayoutCurve:
    if regime == "top_1":
        return PayoutCurve(
            percentile_to_payout={0.001: 50.0, 0.005: 20.0, 0.01: 10.0, 0.05: 2.0},
            regime="top_1",
            cash_line_percentile=0.05,
        )
    if regime == "top_50":
        return PayoutCurve(
            percentile_to_payout={0.5: 1.8},
            regime="top_50",
            cash_line_percentile=0.5,
        )
    # default: top_20
    return PayoutCurve(
        percentile_to_payout={
            0.01: 8.0,
            0.05: 3.0,
            0.10: 2.0,
            0.20: 1.4,
        },
        regime="top_20",
        cash_line_percentile=0.20,
    )


def load_curve_from_archive(slate_date: str) -> PayoutCurve | None:
    """Attempt to load `data/contest_payouts/contest_*_{slate_date}.json`
    and translate `info.rankDisplayInfos` into a PayoutCurve.

    Returns None on miss or empty schedule (pregame).
    """
    if not PAYOUT_ARCHIVE_DIR.exists():
        return None
    for p in sorted(PAYOUT_ARCHIVE_DIR.glob(f"*_{slate_date}.json")):
        try:
            raw = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        rdi = (raw.get("info") or {}).get("rankDisplayInfos") or []
        if not rdi:
            continue
        schedule: dict[float, float] = {}
        for entry in rdi:
            # entry shape from MLB precedent: {threshold: float, payout: float}
            t = entry.get("threshold") or entry.get("percentile")
            payout = entry.get("payout") or entry.get("multiplier")
            if t is None or payout is None:
                continue
            try:
                schedule[float(t)] = float(payout)
            except (TypeError, ValueError):
                continue
        if schedule:
            return PayoutCurve(
                percentile_to_payout=schedule,
                regime="archive",
                cash_line_percentile=max(schedule.keys()),
            )
    return None


def expected_payout(
    own_samples: np.ndarray,
    field_score_samples: np.ndarray,
    curve: PayoutCurve,
    *,
    field_size: int | None = None,
) -> float:
    """Monte Carlo EV.

    own_samples       : (n_samples,) score samples for the candidate lineup.
    field_score_samples : (n_field, n_samples) field-lineup scores; n_field
                          rows of (n_samples,) score samples per opponent.

    Strategy: for each sample s, compute the candidate's rank within
    [own_samples[s]] ∪ field_score_samples[:, s].
    """
    if own_samples.size == 0 or field_score_samples.size == 0:
        return 0.0
    n_field, n_samples = field_score_samples.shape
    field_size = field_size or (n_field + 1)
    payouts = np.zeros(n_samples)
    for s in range(n_samples):
        field_scores = field_score_samples[:, s]
        own_score = own_samples[s]
        # Rank = number of field lineups scoring at least as high (0-indexed)
        rank = int(np.sum(field_scores > own_score))
        payouts[s] = curve.payout_for_rank(rank, field_size)
    return float(payouts.mean())
