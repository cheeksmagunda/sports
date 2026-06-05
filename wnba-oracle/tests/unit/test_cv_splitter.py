"""WalkForwardSplitter invariants."""

from __future__ import annotations

import datetime as dt

import polars as pl

from wnba_oracle.eval.cv import (
    DEFAULT_EMBARGO_DAYS,
    LONGEST_ROLLING_WINDOW_GAMES,
    WalkForwardSplitter,
)


def _synthetic_df(n_days: int = 100) -> pl.DataFrame:
    base = dt.date(2026, 5, 1)
    rows = []
    for d in range(n_days):
        for i in range(5):
            rows.append({"slate_date": (base + dt.timedelta(days=d)).isoformat(), "x": d * 5 + i})
    return pl.from_dicts(rows)


def test_folds_have_no_overlap_and_respect_embargo() -> None:
    df = _synthetic_df()
    s = WalkForwardSplitter(n_folds=4, embargo_days=3, min_train_days=10)
    folds = list(s.split(df))
    assert len(folds) > 0
    for train_idx, eval_idx in folds:
        assert not (set(train_idx) & set(eval_idx))
        # Train rows must be earlier than eval rows
        train_dates = {df[i]["slate_date"][0] for i in train_idx[-5:]}
        eval_dates = {df[i]["slate_date"][0] for i in eval_idx[:5]}
        max_train = max(dt.date.fromisoformat(d) for d in train_dates)
        min_eval = min(dt.date.fromisoformat(d) for d in eval_dates)
        assert (min_eval - max_train).days >= 1


def test_empty_df_yields_no_folds() -> None:
    s = WalkForwardSplitter()
    assert list(s.split(pl.DataFrame({"slate_date": []}))) == []


def test_default_embargo_covers_longest_rolling_window() -> None:
    # The default embargo must span the calendar length of the longest
    # per-player rolling window (~L20), not a token few days (#0a, D63).
    assert DEFAULT_EMBARGO_DAYS >= LONGEST_ROLLING_WINDOW_GAMES * 3  # >= 60d
    assert WalkForwardSplitter().embargo_days == DEFAULT_EMBARGO_DAYS


def test_folds_respect_configured_embargo() -> None:
    # The gap between the last train date and the first eval date of every
    # fold must be >= embargo_days (not merely >= 1).
    df = _synthetic_df(n_days=400)
    s = WalkForwardSplitter(n_folds=4, embargo_days=DEFAULT_EMBARGO_DAYS, min_train_days=21)
    folds = list(s.split(df))
    assert len(folds) > 0
    for train_idx, eval_idx in folds:
        max_train = max(dt.date.fromisoformat(df[i]["slate_date"][0]) for i in train_idx)
        min_eval = min(dt.date.fromisoformat(df[i]["slate_date"][0]) for i in eval_idx)
        assert (min_eval - max_train).days >= s.embargo_days


def test_for_rolling_window_constructor() -> None:
    s = WalkForwardSplitter.for_rolling_window(20, days_per_game=3.5)
    assert s.embargo_days == 70
