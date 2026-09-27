"""Season walk-forward evaluation of Real value baselines (OOS by season)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from nhl_oracle.baselines.metrics import RegressionMetrics, regression_metrics
from nhl_oracle.baselines.priors import BaselineKind, HistoricalPriorBaseline
from nhl_oracle.contract.boost_gate import evaluate_boost_eligibility
from nhl_oracle.labels.hv import TRAINING_LABEL_SECTION, filter_train_labels_to_hv
from nhl_oracle.labels.schema import ValueLabel

DEFAULT_BASELINES: tuple[BaselineKind, ...] = (
    "global_mean",
    "position_mean",
    "player_mean",
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
            "boost_regime": "none",
            "train_label_section": TRAINING_LABEL_SECTION,
        }


def _seasons(labels: Sequence[ValueLabel]) -> list[int]:
    return sorted({row.season for row in labels})


def evaluate_walk_forward(
    labels: Sequence[ValueLabel],
    *,
    baselines: Sequence[BaselineKind] = DEFAULT_BASELINES,
    min_train_seasons: int = 1,
    team_games_played: dict[str, int] | None = None,
    prefer_hv_section: bool = True,
) -> WalkForwardReport:
    """Evaluate priors OOS: train on seasons strictly earlier than test season.

    When ``prefer_hv_section`` is true and any row is tagged
    ``highestBoostedValuePlayers``, evaluation uses only that HV subset
    (#535). If no HV-tagged rows exist, falls back to the full label set and
    notes the corpus gap. Reports honest MAE/RMSE without claiming contest
    decision value. Goalie ``G`` is included in position buckets when present.
    Boost regime stays ``none`` while the all-teams-played gate is closed.
    """

    eligibility = evaluate_boost_eligibility(team_games_played)
    boost_regime = "none"

    working: Sequence[ValueLabel] = labels
    hv_only = filter_train_labels_to_hv(labels) if prefer_hv_section else ()
    used_hv = bool(hv_only)
    if used_hv:
        working = hv_only

    seasons = _seasons(working)
    notes: list[str] = [
        "Walk-forward by season on NHL Real value labels (shadow / observation).",
        "No contest submission or live entry code paths are exercised.",
        "Unseen positions fall back to the global prior from the train window.",
        "player_mean falls back to position then global.",
        (
            f"Boost regime {boost_regime}: hard-gated none until every team has "
            ">=1 GP; early-season gap before that is the edge - do not design "
            "picker logic around card boosts yet."
        ),
        eligibility.detail,
        "Goalie position G is eligible when present in labels.",
        f"train_label_section={TRAINING_LABEL_SECTION}",
    ]
    if used_hv:
        notes.append(
            f"Using {len(working)} HV-tagged labels "
            f"(section={TRAINING_LABEL_SECTION}); never winning drafts."
        )
    elif prefer_hv_section:
        notes.append(
            "HV corpus gap: no highestBoostedValuePlayers-tagged labels; "
            "falling back to unsectioned value rows for this run."
        )
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
        train_rows = [row for row in working if row.season in train_seasons]
        test_rows = [row for row in working if row.season == test_season]
        if not test_rows:
            continue
        for kind in baselines:
            prior = HistoricalPriorBaseline(kind=kind).fit(train_rows)
            preds = prior.predict(test_rows)
            actuals = [row.value for row in test_rows]
            metrics = regression_metrics(actuals, preds)
            folds.append(
                FoldResult(
                    test_season=test_season,
                    train_seasons=train_seasons,
                    kind=kind,
                    metrics=metrics,
                    n_train=prior.n_train,
                    n_positions=prior.n_positions,
                    global_prior=prior.global_prior,
                )
            )
            pooled_actual, pooled_pred = pooled_pairs[kind]
            pooled_actual.extend(actuals)
            pooled_pred.extend(preds)

    pooled = {
        kind: regression_metrics(actuals, preds) for kind, (actuals, preds) in pooled_pairs.items()
    }
    return WalkForwardReport(
        baselines=tuple(baselines),
        folds=tuple(folds),
        pooled=pooled,
        n_labels=len(working),
        seasons=tuple(seasons),
        notes=tuple(notes),
    )
