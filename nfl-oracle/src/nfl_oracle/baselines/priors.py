"""Transparent historical priors for Real ``value`` (no fancy models)."""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from nfl_oracle.labels.schema import ValueLabel

BaselineKind = Literal[
    "global_mean",
    "position_mean",
    "position_median",
    "player_mean",
]


@dataclass
class HistoricalPriorBaseline:
    """Fit mean/median priors on earlier seasons only.

    Unseen positions/players fall back to the global prior. Empty training
    yields a constant 0.0 predictor so evaluation still reports honest
    empty/sparse folds without crashing.
    """

    kind: BaselineKind
    global_prior: float = 0.0
    position_priors: dict[str, float] = field(default_factory=dict)
    player_priors: dict[int, float] = field(default_factory=dict)
    n_train: int = 0
    n_positions: int = 0
    n_players: int = 0

    def fit(self, labels: Sequence[ValueLabel]) -> HistoricalPriorBaseline:
        values = [row.value for row in labels]
        self.n_train = len(values)
        if not values:
            self.global_prior = 0.0
            self.position_priors = {}
            self.player_priors = {}
            self.n_positions = 0
            self.n_players = 0
            return self
        self.global_prior = float(statistics.fmean(values))
        by_pos: dict[str, list[float]] = defaultdict(list)
        by_player: dict[int, list[float]] = defaultdict(list)
        for row in labels:
            by_pos[row.position].append(row.value)
            by_player[row.player_id].append(row.value)
        priors: dict[str, float] = {}
        for position, series in by_pos.items():
            if self.kind == "position_median":
                priors[position] = float(statistics.median(series))
            else:
                priors[position] = float(statistics.fmean(series))
        self.position_priors = priors
        self.n_positions = len(priors)
        self.player_priors = {
            pid: float(statistics.fmean(series)) for pid, series in by_player.items() if series
        }
        self.n_players = len(self.player_priors)
        return self

    def predict_one(self, position: str, player_id: int | None = None) -> float:
        if self.kind == "global_mean":
            return self.global_prior
        if self.kind == "player_mean":
            if player_id is not None and player_id in self.player_priors:
                return self.player_priors[player_id]
            return self.position_priors.get(position, self.global_prior)
        return self.position_priors.get(position, self.global_prior)

    def predict(self, labels: Iterable[ValueLabel]) -> list[float]:
        return [self.predict_one(row.position, row.player_id) for row in labels]

    def summary(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "n_train": self.n_train,
            "n_positions": self.n_positions,
            "n_players": self.n_players,
            "global_prior": self.global_prior,
            "position_priors": dict(sorted(self.position_priors.items())),
            "player_prior_count": self.n_players,
        }
