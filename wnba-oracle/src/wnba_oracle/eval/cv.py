"""Walk-forward purged + embargoed cross-validation.

Random K-fold leaks. Time is the boundary. Each fold:
    train = [start, t_train_end)
    embargo = [t_train_end, t_train_end + embargo_days)
    eval = [t_train_end + embargo_days, t_eval_end)

The embargo gap prevents per-player rolling features that span the
boundary from leaking the label.

`WalkForwardSplitter.split(df, date_col)` yields (train_idx, eval_idx)
tuples. Unit-tested in tests/unit/test_cv_splitter.py:

    - No fold has overlap between train and eval index arrays.
    - Every fold leaves a >= embargo_days gap.
    - Folds are ordered by time.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True)
class WalkForwardSplitter:
    n_folds: int = 5
    embargo_days: int = 3
    min_train_days: int = 21

    def split(
        self,
        df: pl.DataFrame,
        date_col: str = "slate_date",
    ) -> Iterator[tuple[list[int], list[int]]]:
        if df.is_empty():
            return
        dates = df.get_column(date_col).cast(pl.String).to_list()
        parsed = sorted({dt.date.fromisoformat(s) for s in dates if s})
        if len(parsed) < self.n_folds + 2:
            return
        total_days = (parsed[-1] - parsed[0]).days
        fold_span = max(1, (total_days - self.min_train_days) // self.n_folds)
        for fold in range(self.n_folds):
            train_end = parsed[0] + dt.timedelta(
                days=self.min_train_days + fold * fold_span
            )
            eval_start = train_end + dt.timedelta(days=self.embargo_days)
            eval_end = eval_start + dt.timedelta(days=fold_span)
            if eval_end > parsed[-1]:
                eval_end = parsed[-1] + dt.timedelta(days=1)
            train_idx: list[int] = []
            eval_idx: list[int] = []
            for i, d in enumerate(dates):
                try:
                    di = dt.date.fromisoformat(d)
                except (TypeError, ValueError):
                    continue
                if di < train_end:
                    train_idx.append(i)
                elif eval_start <= di < eval_end:
                    eval_idx.append(i)
            if not train_idx or not eval_idx:
                continue
            yield train_idx, eval_idx
