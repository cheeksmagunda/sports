"""WalkForwardSplitter invariants."""

from __future__ import annotations

import datetime as dt

import polars as pl

from wnba_oracle.eval.cv import WalkForwardSplitter


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
