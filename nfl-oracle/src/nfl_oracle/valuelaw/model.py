"""Fit and apply the box-stats-to-value model.

Corpus G's ``value`` label is not a pure function of the visible box score
(see ``box_stats_label_report.json``'s ``purity`` block: about 5% of variance
is unexplained even holding the exact stat line fixed), but the explainable
share is very large. This module fits one linear model per position family on
:mod:`nfl_oracle.valuelaw.boxstats`'s flat dataset and reports out-of-sample
accuracy against named baselines, so "the box score explains value" is a
tested claim, not an assertion.

Split is strictly time-aware: train on season 2024 regular-season rows, test
on season 2025 regular-season rows. Preseason rows are excluded from both, to
match the STATUS.md convention (37,710 of 47,209 rows are non-preseason).
Nothing here reads a 2025 row to inform a prediction for another 2025 row from
an earlier week; the split is by season, which is what the data on disk
supports today. A finer walk-forward-by-week split is future work.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oracle_core.artifacts import atomic_write_json

from nfl_oracle.baselines.ridge import RidgeRegressor

STAT_COLUMN_RE = re.compile(r"^(stat|adv)_\d+(_\w+)?$")

POSITION_FAMILIES: dict[str, tuple[str, ...]] = {
    "offense": ("QB", "RB", "WR", "TE"),
    "defense": ("DL", "LB", "DB"),
    "special_teams": ("K", "P"),
}


def _family_for(position: str) -> str | None:
    for family, positions in POSITION_FAMILIES.items():
        if position in positions:
            return family
    return None


@dataclass(frozen=True)
class PositionModel:
    position: str
    feature_names: tuple[str, ...]
    coefficients: tuple[float, ...]
    train_rows: int
    train_season: int
    test_season: int
    test_rows: int
    test_r2: float
    test_mae: float
    test_rmse: float
    baseline_position_mean_mae: float
    residual_sd: float

    def predict(self, stats: Mapping[str, float | None]) -> float:
        row = [1.0] + [float(stats.get(name) or 0.0) for name in self.feature_names]
        return sum(c * v for c, v in zip(self.coefficients, row, strict=True))


@dataclass(frozen=True)
class ValueModelBundle:
    models: dict[str, PositionModel]
    dataset_row_count: int
    dataset_sha256: str | None

    def predict(self, position: str, stats: Mapping[str, float | None]) -> float | None:
        model = self.models.get(position)
        return model.predict(stats) if model else None


def _load_rows(dataset_path: Path) -> list[dict[str, Any]]:
    rows = []
    with dataset_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _feature_names(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    names: set[str] = set()
    for row in rows:
        for key, value in row.items():
            if value is not None and STAT_COLUMN_RE.match(key):
                names.add(key)
    return sorted(names)


def _design_matrix(
    rows: Sequence[Mapping[str, Any]], feature_names: Sequence[str]
) -> list[list[float]]:
    return [[1.0] + [float(row.get(name) or 0.0) for name in feature_names] for row in rows]


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def fit_position_model(
    rows: Sequence[Mapping[str, Any]],
    *,
    position: str,
    train_season: int,
    test_season: int,
    alpha: float = 1e-6,
) -> PositionModel | None:
    pos_rows = [
        r
        for r in rows
        if r.get("position") == position
        and not r.get("did_not_play")
        and r.get("box_value") is not None
        and r.get("season_type") != "preseason"
    ]
    train = [r for r in pos_rows if r.get("season") == train_season]
    test = [r for r in pos_rows if r.get("season") == test_season]
    if len(train) < 10 or len(test) < 5:
        return None

    feature_names = _feature_names(train)
    x_train = _design_matrix(train, feature_names)
    y_train = [float(r["box_value"]) for r in train]
    model = RidgeRegressor(alpha=alpha).fit(x_train, y_train)

    x_test = _design_matrix(test, feature_names)
    y_test = [float(r["box_value"]) for r in test]
    preds = model.predict(x_test)
    residuals = [p - y for p, y in zip(preds, y_test, strict=True)]
    mae = _mean(abs(r) for r in residuals)
    rmse = _mean(r * r for r in residuals) ** 0.5
    y_train_mean = _mean(y_train)
    ss_res = sum(r * r for r in residuals)
    ss_tot = sum((y - y_train_mean) ** 2 for y in y_test)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    position_mean_mae = _mean(abs(y - y_train_mean) for y in y_test)
    residual_sd = (sum((r - _mean(residuals)) ** 2 for r in residuals) / len(residuals)) ** 0.5

    return PositionModel(
        position=position,
        feature_names=tuple(feature_names),
        coefficients=tuple(model.coefficients or []),
        train_rows=len(train),
        train_season=train_season,
        test_season=test_season,
        test_rows=len(test),
        test_r2=r2,
        test_mae=mae,
        test_rmse=rmse,
        baseline_position_mean_mae=position_mean_mae,
        residual_sd=residual_sd,
    )


def fit_all(
    dataset_path: Path,
    *,
    train_season: int = 2024,
    test_season: int = 2025,
) -> ValueModelBundle:
    rows = _load_rows(dataset_path)
    positions = sorted({r["position"] for r in rows if r.get("position")})
    models: dict[str, PositionModel] = {}
    for position in positions:
        fitted = fit_position_model(
            rows, position=position, train_season=train_season, test_season=test_season
        )
        if fitted is not None:
            models[position] = fitted
    return ValueModelBundle(models=models, dataset_row_count=len(rows), dataset_sha256=None)


def bundle_to_json(bundle: ValueModelBundle) -> dict[str, Any]:
    return {
        "dataset_row_count": bundle.dataset_row_count,
        "positions": {
            pos: {
                "feature_names": list(model.feature_names),
                "coefficients": list(model.coefficients),
                "train_rows": model.train_rows,
                "train_season": model.train_season,
                "test_season": model.test_season,
                "test_rows": model.test_rows,
                "test_r2": model.test_r2,
                "test_mae": model.test_mae,
                "test_rmse": model.test_rmse,
                "baseline_position_mean_mae": model.baseline_position_mean_mae,
                "residual_sd": model.residual_sd,
            }
            for pos, model in bundle.models.items()
        },
    }


def bundle_from_json(payload: Mapping[str, Any]) -> ValueModelBundle:
    models = {}
    for pos, data in payload["positions"].items():
        models[pos] = PositionModel(
            position=pos,
            feature_names=tuple(data["feature_names"]),
            coefficients=tuple(data["coefficients"]),
            train_rows=data["train_rows"],
            train_season=data["train_season"],
            test_season=data["test_season"],
            test_rows=data["test_rows"],
            test_r2=data["test_r2"],
            test_mae=data["test_mae"],
            test_rmse=data["test_rmse"],
            baseline_position_mean_mae=data["baseline_position_mean_mae"],
            residual_sd=data["residual_sd"],
        )
    return ValueModelBundle(
        models=models, dataset_row_count=payload["dataset_row_count"], dataset_sha256=None
    )


def write_bundle(bundle: ValueModelBundle, path: Path) -> None:
    atomic_write_json(path, bundle_to_json(bundle))


def load_bundle(path: Path) -> ValueModelBundle:
    with path.open(encoding="utf-8") as fh:
        return bundle_from_json(json.load(fh))
