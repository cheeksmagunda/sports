"""Season walk-forward evaluation of Real value baselines (OOS by season)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from nfl_oracle.baselines.metrics import RegressionMetrics, regression_metrics
from nfl_oracle.baselines.priors import BaselineKind, HistoricalPriorBaseline
from nfl_oracle.labels.schema import ValueLabel

DEFAULT_BASELINES: tuple[BaselineKind, ...] = (
    "global_mean",
    "position_mean",
    "position_median",
)


@dataclass(frozen=True)
class FoldResult:
    test_season: int
    train_seasons: tuple[int, ...]
    kind: BaselineKind
    metrics: RegressionMetrics
    n_train: int
    n_positions: int
    global_prior: float

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["train_seasons"] = list(self.train_seasons)
        payload["metrics"] = self.metrics.to_dict()
        return payload


@dataclass(frozen=True)
class WalkForwardReport:
    baselines: tuple[BaselineKind, ...]
    folds: tuple[FoldResult, ...]
    pooled: dict[BaselineKind, RegressionMetrics]
    n_labels: int
    seasons: tuple[int, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "baselines": list(self.baselines),
            "n_labels": self.n_labels,
            "seasons": list(self.seasons),
            "notes": list(self.notes),
            "folds": [fold.to_dict() for fold in self.folds],
            "pooled": {kind: metrics.to_dict() for kind, metrics in self.pooled.items()},
            "observation_only": True,
            "contest_entry": False,
        }


def _seasons(labels: Sequence[ValueLabel]) -> list[int]:
    return sorted({row.season for row in labels})


def evaluate_walk_forward(
    labels: Sequence[ValueLabel],
    *,
    baselines: Sequence[BaselineKind] = DEFAULT_BASELINES,
    min_train_seasons: int = 1,
) -> WalkForwardReport:
    """Evaluate priors OOS: train on seasons < test season.

    Sparse Corpus G anchors make position priors noisy; pooled MAE/RMSE are
    reported honestly without claiming contest decision value.
    """

    seasons = _seasons(labels)
    notes: list[str] = [
        "Walk-forward by season on Corpus G anchors only (shadow / observation).",
        "No contest submission or live entry code paths are exercised.",
        "Unseen positions fall back to the global prior from the train window.",
        "player_mean falls back to position then global; "
        "identity continuity across anchors is unaudited.",
    ]
    if len(seasons) < 2:
        notes.append("Fewer than two seasons present; no OOS fold can be formed.")

    folds: list[FoldResult] = []
    pooled_pairs: dict[BaselineKind, tuple[list[float], list[float]]] = {
        kind: ([], []) for kind in baselines
    }

    for idx, test_season in enumerate(seasons):
        train_seasons = tuple(seasons[:idx])
        if len(train_seasons) < min_train_seasons:
            continue
        train_rows = [row for row in labels if row.season in train_seasons]
        test_rows = [row for row in labels if row.season == test_season]
        if not test_rows:
            continue
        for kind in baselines:
            model = HistoricalPriorBaseline(kind=kind).fit(train_rows)
            preds = model.predict(test_rows)
            actuals = [row.value for row in test_rows]
            metrics = regression_metrics(actuals, preds)
            folds.append(
                FoldResult(
                    test_season=test_season,
                    train_seasons=train_seasons,
                    kind=kind,
                    metrics=metrics,
                    n_train=model.n_train,
                    n_positions=model.n_positions,
                    global_prior=model.global_prior,
                )
            )
            pooled_pairs[kind][0].extend(actuals)
            pooled_pairs[kind][1].extend(preds)

    pooled = {
        kind: regression_metrics(actuals, preds) for kind, (actuals, preds) in pooled_pairs.items()
    }
    return WalkForwardReport(
        baselines=tuple(baselines),
        folds=tuple(folds),
        pooled=pooled,
        n_labels=len(labels),
        seasons=tuple(seasons),
        notes=tuple(notes),
    )
