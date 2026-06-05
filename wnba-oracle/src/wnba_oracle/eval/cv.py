"""Walk-forward purged + embargoed cross-validation.

Random K-fold leaks. Time is the boundary. Each fold:
    train = [start, t_train_end)
    embargo = [t_train_end, t_train_end + embargo_days)
    eval = [t_train_end + embargo_days, t_eval_end)

The embargo must be at least as long as the calendar span of the longest
per-player rolling feature window, so the validation estimate reflects the
*forward* prediction distance the picker actually faces (train on the
season-to-date, predict tonight) rather than near-adjacent games that share a
player's recent form. The dominant windows live in features/spec.py: L5/L10
plus an L20 (``mins_l20``, ``coach_rotation_consistency_l20``). Over WNBA's
sparse schedule one team plays ~every 3.5 calendar days, so an L20 window spans
~70 days; a 3-day gap (the pre-D63 default) left train and eval rows highly
autocorrelated and made every walk-forward number optimistic. ``embargo_days``
now defaults to that window-covering span (see ``DEFAULT_EMBARGO_DAYS`` /
``for_rolling_window``).

Note: this enlarged embargo is defense-in-depth. The primary protection is that
the corpus builder computes rolling features strictly causally per row
(``game_date < as_of_date``), so no future game ever enters a row's features.

``WalkForwardSplitter.split(df, date_col)`` yields (train_idx, eval_idx)
tuples. Unit-tested in tests/unit/test_cv_splitter.py:

    - No fold has overlap between train and eval index arrays.
    - Every fold leaves a >= embargo_days gap.
    - Folds are ordered by time.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Iterator
from dataclasses import dataclass

import polars as pl

# Longest per-player rolling-feature window in games (mins_l20,
# coach_rotation_consistency_l20 in features/spec.py).
LONGEST_ROLLING_WINDOW_GAMES = 20
# WNBA single-team game cadence: ~44 games over a ~140-day regular season
# (2025) => ~3.5 calendar days per game. Translates a game-count window into the
# calendar embargo that fully separates it.
WNBA_DAYS_PER_GAME = 3.5
DEFAULT_EMBARGO_DAYS = math.ceil(LONGEST_ROLLING_WINDOW_GAMES * WNBA_DAYS_PER_GAME)


@dataclass(frozen=True)
class WalkForwardSplitter:
    n_folds: int = 5
    embargo_days: int = DEFAULT_EMBARGO_DAYS
    min_train_days: int = 21

    @classmethod
    def for_rolling_window(
        cls,
        window_games: int,
        *,
        days_per_game: float = WNBA_DAYS_PER_GAME,
        n_folds: int = 5,
        min_train_days: int = 21,
    ) -> WalkForwardSplitter:
        """Splitter whose embargo covers a ``window_games``-game feature window.

        Lets a denser corpus (the ~13k game-logs) request full L20 coverage
        while a caller on a sparser frame can pass a smaller window.
        """
        return cls(
            n_folds=n_folds,
            embargo_days=math.ceil(window_games * days_per_game),
            min_train_days=min_train_days,
        )

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
