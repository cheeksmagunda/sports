"""Leakage-safe feature-driven Real value model (optional walk-forward method).

Uses only live_ok prior / identity / calendar-agnostic features derived from
training seasons strictly earlier than the decision/test season. Never reads
same-slate finals or the label ``value`` as an input feature.

Stdlib ridge only — no numpy/sklearn required so the default offline path stays
light. Observation / research only; no contest entry.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from nfl_oracle.baselines.ridge import RidgeRegressor
from nfl_oracle.features.schema import live_ok_feature_names
from nfl_oracle.labels.schema import LIVE_FEATURE_BLACKLIST, ValueLabel

# Canonical positions; residual bucket is the reference (all zeros).
_POSITION_ONE_HOT: tuple[str, ...] = ("QB", "RB", "WR", "TE", "K")

# Live-ok numeric / categorical inputs this model actually consumes.
MODEL_FEATURE_NAMES: tuple[str, ...] = (
    "intercept",
    "player_prior_mean",
    "position_prior_mean",
    "position_prior_median",
    "global_prior_mean",
    "team_prior_mean",
    "prior_n_games",
    "pos_QB",
    "pos_RB",
    "pos_WR",
    "pos_TE",
    "pos_K",
)

FORBIDDEN_FEATURE_NAMES: frozenset[str] = frozenset(
    {
        "value",
        "same_slate_final_value",
        "card_boost_post_settlement",
        *LIVE_FEATURE_BLACKLIST,
    }
)


def assert_model_features_leakage_safe() -> None:
    """Raise if the model feature set intersects the live blacklist / labels."""

    live_ok = set(live_ok_feature_names())
    for name in MODEL_FEATURE_NAMES:
        if name in FORBIDDEN_FEATURE_NAMES:
            raise AssertionError(f"forbidden feature in value model: {name}")
        if name in {"intercept", "pos_QB", "pos_RB", "pos_WR", "pos_TE", "pos_K"}:
            continue
        if name not in live_ok:
            raise AssertionError(f"value model feature not live_ok: {name}")


@dataclass
class _PriorBank:
    global_mean: float = 0.0
    position_mean: dict[str, float] = field(default_factory=dict)
    position_median: dict[str, float] = field(default_factory=dict)
    player_mean: dict[int, float] = field(default_factory=dict)
    player_n: dict[int, int] = field(default_factory=dict)
    team_mean: dict[int, float] = field(default_factory=dict)


def _fit_prior_bank(labels: Sequence[ValueLabel]) -> _PriorBank:
    values = [row.value for row in labels]
    bank = _PriorBank()
    if not values:
        return bank
    bank.global_mean = float(statistics.fmean(values))
    by_pos: dict[str, list[float]] = defaultdict(list)
    by_player: dict[int, list[float]] = defaultdict(list)
    by_team: dict[int, list[float]] = defaultdict(list)
    for row in labels:
        by_pos[row.position].append(row.value)
        by_player[row.player_id].append(row.value)
        if row.team_id is not None:
            by_team[row.team_id].append(row.value)
    bank.position_mean = {p: float(statistics.fmean(vs)) for p, vs in by_pos.items() if vs}
    bank.position_median = {p: float(statistics.median(vs)) for p, vs in by_pos.items() if vs}
    bank.player_mean = {pid: float(statistics.fmean(vs)) for pid, vs in by_player.items() if vs}
    bank.player_n = {pid: len(vs) for pid, vs in by_player.items()}
    bank.team_mean = {tid: float(statistics.fmean(vs)) for tid, vs in by_team.items() if vs}
    return bank


def _vector_from_bank(row: ValueLabel, bank: _PriorBank) -> list[float]:
    pos_mean = bank.position_mean.get(row.position, bank.global_mean)
    pos_med = bank.position_median.get(row.position, bank.global_mean)
    if row.player_id in bank.player_mean:
        player_prior = bank.player_mean[row.player_id]
        n_games = float(bank.player_n.get(row.player_id, 0))
    else:
        player_prior = pos_mean
        n_games = 0.0
    if row.team_id is not None and row.team_id in bank.team_mean:
        team_prior = bank.team_mean[row.team_id]
    else:
        team_prior = bank.global_mean
    one_hot = [1.0 if row.position == p else 0.0 for p in _POSITION_ONE_HOT]
    return [
        1.0,
        float(player_prior),
        float(pos_mean),
        float(pos_med),
        float(bank.global_mean),
        float(team_prior),
        math.log1p(n_games),
        *one_hot,
    ]


@dataclass
class FeatureDrivenValueModel:
    """Ridge on walk-forward prior features; duck-types HistoricalPriorBaseline attrs."""

    alpha: float = 1.0
    global_prior: float = 0.0
    n_train: int = 0
    n_positions: int = 0
    n_features: int = 0
    feature_names: tuple[str, ...] = MODEL_FEATURE_NAMES
    _bank: _PriorBank = field(default_factory=_PriorBank, repr=False)
    _ridge: RidgeRegressor = field(default_factory=RidgeRegressor, repr=False)
    kind: str = "feature_ridge"

    def fit(self, labels: Sequence[ValueLabel]) -> FeatureDrivenValueModel:
        assert_model_features_leakage_safe()
        self._bank = _fit_prior_bank(labels)
        self.global_prior = self._bank.global_mean
        self.n_train = len(labels)
        self.n_positions = len(self._bank.position_mean)
        x = [_vector_from_bank(row, self._bank) for row in labels]
        y = [row.value for row in labels]
        self.n_features = len(MODEL_FEATURE_NAMES)
        self._ridge = RidgeRegressor(alpha=self.alpha).fit(x, y)
        if not labels:
            # Empty train → constant 0 predictor (honest sparse fold).
            self._ridge.coefficients = [0.0] * self.n_features
        return self

    def design_matrix(self, labels: Sequence[ValueLabel]) -> list[list[float]]:
        """Build feature rows using **fit-time** prior bank only (no label peek)."""

        return [_vector_from_bank(row, self._bank) for row in labels]

    def predict(self, labels: Iterable[ValueLabel]) -> list[float]:
        rows = list(labels)
        if self.n_train == 0:
            return [0.0] * len(rows)
        return self._ridge.predict(self.design_matrix(rows))

    def predict_one(
        self,
        position: str,
        player_id: int | None = None,
        *,
        team_id: int | None = None,
        season: int = 0,
        game_id: int = 0,
    ) -> float:
        label = ValueLabel(
            player_id=player_id if player_id is not None else -1,
            game_id=game_id,
            season=season,
            position=position,
            value=0.0,  # ignored for features
            team_id=team_id,
        )
        return self.predict([label])[0]

    def summary(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "n_train": self.n_train,
            "n_positions": self.n_positions,
            "n_features": self.n_features,
            "feature_names": list(self.feature_names),
            "global_prior": self.global_prior,
            "alpha": self.alpha,
            "coefficients": list(self._ridge.coefficients or []),
            "observation_only": True,
            "contest_entry": False,
        }


def fit_feature_value_model(
    train_labels: Sequence[ValueLabel],
    *,
    alpha: float = 1.0,
) -> FeatureDrivenValueModel:
    return FeatureDrivenValueModel(alpha=alpha).fit(train_labels)
