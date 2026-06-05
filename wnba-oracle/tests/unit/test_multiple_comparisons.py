"""Multiple-comparisons guard: CPCV splitter + deflated-edge test (D63)."""

from __future__ import annotations

import datetime as dt
import math

import numpy as np
import polars as pl

from wnba_oracle.eval.multiple_comparisons import (
    CombinatorialPurgedCV,
    deflated_edge,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)


def _df(n_days: int = 120) -> pl.DataFrame:
    base = dt.date(2025, 5, 16)
    rows = [
        {"slate_date": (base + dt.timedelta(days=d)).isoformat(), "x": d}
        for d in range(n_days)
        for _ in range(4)
    ]
    return pl.from_dicts(rows)


def test_cpcv_yields_expected_number_of_paths() -> None:
    cv = CombinatorialPurgedCV(n_groups=6, n_test_groups=2, embargo_days=7)
    folds = list(cv.split(_df()))
    # C(6, 2) = 15 combinations; all should be non-empty on a 120-day frame.
    assert len(folds) == 15
    for train_idx, test_idx in folds:
        assert not (set(train_idx) & set(test_idx))
        assert train_idx and test_idx


def test_cpcv_purges_embargo_around_test_blocks() -> None:
    df = _df()
    embargo = 10
    # Single contiguous test block so [min, max] is the exact block span and the
    # per-block purge can be checked against the envelope.
    cv = CombinatorialPurgedCV(n_groups=6, n_test_groups=1, embargo_days=embargo)
    dates = df.get_column("slate_date").to_list()
    for train_idx, test_idx in cv.split(df):
        test_dates = [dt.date.fromisoformat(dates[i]) for i in test_idx]
        lo, hi = min(test_dates), max(test_dates)
        for i in train_idx:
            d = dt.date.fromisoformat(dates[i])
            # No train row may sit within the embargo window of the test block.
            assert not (lo - dt.timedelta(days=embargo) <= d <= hi + dt.timedelta(days=embargo))


def test_psr_increases_with_clean_positive_edge() -> None:
    rng = np.random.default_rng(0)
    weak = rng.normal(0.02, 1.0, 200)
    strong = rng.normal(0.40, 1.0, 200)
    assert probabilistic_sharpe_ratio(strong) > probabilistic_sharpe_ratio(weak)


def test_expected_max_sharpe_grows_with_trials() -> None:
    v = 0.04
    assert expected_max_sharpe(50, v) > expected_max_sharpe(2, v)
    assert expected_max_sharpe(10, 0.0) == 0.0


def test_deflated_edge_punishes_many_trials() -> None:
    rng = np.random.default_rng(1)
    improvement = rng.normal(0.15, 1.0, 130)  # a real but modest per-slate edge
    few = deflated_edge(improvement, n_trials=1, trials_sr_var=0.02)
    many = deflated_edge(improvement, n_trials=200, trials_sr_var=0.02)
    # Same data, more trials => higher bar => lower deflated significance.
    assert many.dsr < few.dsr
    assert many.sr0_star > few.sr0_star
    assert math.isclose(few.info_ratio, many.info_ratio)


def test_deflated_edge_rejects_noise() -> None:
    rng = np.random.default_rng(2)
    noise = rng.normal(0.0, 1.0, 130)  # no real edge
    verdict = deflated_edge(noise, n_trials=50, trials_sr_var=0.04, threshold=0.95)
    assert not verdict.passes
