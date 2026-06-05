"""Multiple-comparisons guard for the rotation gate (#MC, D63).

This roadmap runs ~10 gated changes (heads, features, shrinkage constants,
matchup nudges) against one noisy walk-forward harness over ~130 slates with
slate-level correlation. Run that many comparisons and something clears a fixed
CRPS threshold by chance. This module discounts the acceptance bar by the number
of trials, so the gate means what it claims.

Two pieces, both numpy + scipy only:

1. ``CombinatorialPurgedCV`` -- instead of one walk-forward path, evaluate a
   challenger on C(n_groups, n_test_groups) purged+embargoed splits. That yields
   a *distribution* of out-of-sample edges, not a single point estimate, which is
   what the deflated test needs (López de Prado, *Advances in Financial Machine
   Learning*, ch. 7 & 12).

2. ``deflated_edge`` -- the Deflated Sharpe Ratio (Bailey & López de Prado 2014,
   https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf) applied to a
   challenger's per-slate improvement series. It (a) corrects the probabilistic
   Sharpe for non-normal (skewed/heavy-tailed) returns and (b) raises the bar by
   the expected maximum Sharpe under ``n_trials`` independent attempts. A
   challenger "passes" only if its edge survives that deflation.

Sign convention: the improvement series is ``champion_crps - challenger_crps``
per slate, so positive = the challenger is better (lower CRPS is better).
"""

from __future__ import annotations

import datetime as dt
import itertools
import math
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

import numpy as np
import polars as pl
from scipy.stats import norm

from wnba_oracle.eval.cv import DEFAULT_EMBARGO_DAYS

# Euler-Mascheroni constant, used in the expected-maximum-Sharpe estimator.
_EULER_GAMMA = 0.5772156649015329


@dataclass(frozen=True)
class CombinatorialPurgedCV:
    """Combinatorial purged CV over time groups.

    Partitions the distinct dates into ``n_groups`` contiguous blocks and, for
    every choice of ``n_test_groups`` test blocks, yields (train_idx, test_idx)
    with train rows within ``embargo_days`` of any test block purged. Produces
    C(n_groups, n_test_groups) paths.
    """

    n_groups: int = 6
    n_test_groups: int = 2
    embargo_days: int = DEFAULT_EMBARGO_DAYS

    def split(
        self, df: pl.DataFrame, date_col: str = "slate_date"
    ) -> Iterator[tuple[list[int], list[int]]]:
        if df.is_empty():
            return
        dates = df.get_column(date_col).cast(pl.String).to_list()
        parsed: list[dt.date | None] = []
        for s in dates:
            try:
                parsed.append(dt.date.fromisoformat(s) if s else None)
            except (TypeError, ValueError):
                parsed.append(None)
        uniq = sorted({d for d in parsed if d is not None})
        if len(uniq) < self.n_groups:
            return
        # Contiguous, roughly-equal date blocks.
        bounds = np.linspace(0, len(uniq), self.n_groups + 1).astype(int)
        groups: list[tuple[dt.date, dt.date]] = []
        for g in range(self.n_groups):
            block = uniq[bounds[g] : bounds[g + 1]]
            if not block:
                continue
            groups.append((block[0], block[-1]))
        if len(groups) < self.n_test_groups:
            return
        embargo = dt.timedelta(days=self.embargo_days)
        for test_combo in itertools.combinations(range(len(groups)), self.n_test_groups):
            test_ranges = [groups[g] for g in test_combo]
            train_idx: list[int] = []
            test_idx: list[int] = []
            for i, d in enumerate(parsed):
                if d is None:
                    continue
                in_test = any(lo <= d <= hi for lo, hi in test_ranges)
                if in_test:
                    test_idx.append(i)
                    continue
                # Purge: drop train rows within embargo of any test block.
                purged = any(
                    (lo - embargo) <= d <= (hi + embargo) for lo, hi in test_ranges
                )
                if not purged:
                    train_idx.append(i)
            if train_idx and test_idx:
                yield train_idx, test_idx


@dataclass(frozen=True)
class EdgeVerdict:
    """Result of the deflated-edge test for one challenger."""

    n_obs: int
    mean_improvement: float
    info_ratio: float  # per-slate mean/std of improvement (non-annualized SR)
    psr: float  # P(true SR > 0), ignoring trial selection
    dsr: float  # deflated: P(true SR > expected max under n_trials)
    sr0_star: float  # the deflated benchmark Sharpe
    n_trials: int
    passes: bool


def _sharpe(returns: np.ndarray) -> float:
    """Non-annualized Sharpe = mean / std (population-consistent ddof=1)."""
    if returns.size < 2:
        return 0.0
    sd = float(np.std(returns, ddof=1))
    if sd <= 0:
        return 0.0
    return float(np.mean(returns)) / sd


def probabilistic_sharpe_ratio(
    returns: np.ndarray, *, sr_benchmark: float = 0.0
) -> float:
    """PSR: P(true Sharpe > sr_benchmark), corrected for skew/kurtosis.

    Bailey & López de Prado: with observed per-obs Sharpe ``sr``, T observations,
    skewness ``g3`` and (non-excess) kurtosis ``g4``,
        PSR = Phi( (sr - sr_benchmark) * sqrt(T-1)
                   / sqrt(1 - g3*sr + ((g4-1)/4)*sr^2) ).
    """
    t = returns.size
    if t < 3:
        return 0.0
    sr = _sharpe(returns)
    mean = float(np.mean(returns))
    sd = float(np.std(returns, ddof=1))
    if sd <= 0:
        return 1.0 if mean > sr_benchmark else 0.0
    z = (returns - mean) / sd
    g3 = float(np.mean(z**3))
    g4 = float(np.mean(z**4))  # non-excess kurtosis (normal => 3)
    denom = 1.0 - g3 * sr + ((g4 - 1.0) / 4.0) * sr**2
    if denom <= 0:
        return 0.0
    stat = (sr - sr_benchmark) * math.sqrt(t - 1) / math.sqrt(denom)
    return float(norm.cdf(stat))


def expected_max_sharpe(n_trials: int, trials_sr_var: float) -> float:
    """Expected maximum per-obs Sharpe under ``n_trials`` independent attempts.

    SR0* = sqrt(V) * [ (1-gamma) * Z^{-1}(1 - 1/N) + gamma * Z^{-1}(1 - 1/(N*e)) ]
    (Bailey & López de Prado). ``trials_sr_var`` is the variance of the trial
    Sharpe ratios; larger N or larger variance => higher bar.
    """
    n = max(2, int(n_trials))
    v = max(0.0, float(trials_sr_var))
    if v == 0.0:
        return 0.0
    z1 = float(norm.ppf(1.0 - 1.0 / n))
    z2 = float(norm.ppf(1.0 - 1.0 / (n * math.e)))
    return math.sqrt(v) * ((1.0 - _EULER_GAMMA) * z1 + _EULER_GAMMA * z2)


def deflated_edge(
    per_slate_improvement: Sequence[float],
    *,
    n_trials: int,
    trials_sr_var: float,
    threshold: float = 0.95,
) -> EdgeVerdict:
    """Deflated test of a challenger's per-slate CRPS improvement.

    ``per_slate_improvement[i]`` = champion_crps - challenger_crps on slate i
    (positive => challenger better). ``n_trials`` is how many challengers have
    been tried against this harness; ``trials_sr_var`` is the variance of those
    challengers' info ratios (pass the variance of the candidate edges seen so
    far, or a conservative prior). ``passes`` is dsr >= threshold.
    """
    r = np.asarray(list(per_slate_improvement), dtype=float)
    sr0 = expected_max_sharpe(n_trials, trials_sr_var)
    psr = probabilistic_sharpe_ratio(r, sr_benchmark=0.0)
    dsr = probabilistic_sharpe_ratio(r, sr_benchmark=sr0)
    return EdgeVerdict(
        n_obs=int(r.size),
        mean_improvement=float(np.mean(r)) if r.size else 0.0,
        info_ratio=_sharpe(r),
        psr=psr,
        dsr=dsr,
        sr0_star=sr0,
        n_trials=int(n_trials),
        passes=bool(dsr >= threshold),
    )
