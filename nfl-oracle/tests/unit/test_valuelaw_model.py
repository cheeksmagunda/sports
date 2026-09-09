"""Unit tests for nfl_oracle.valuelaw.model."""

from __future__ import annotations

import json
from pathlib import Path

from nfl_oracle.valuelaw.model import (
    bundle_from_json,
    bundle_to_json,
    fit_all,
    fit_position_model,
    load_bundle,
    write_bundle,
)


def _synthetic_rows() -> list[dict[str, object]]:
    """Rows where box_value is an exact linear function of stat_31 (passing yards).

    Real regression should recover the coefficient near-exactly and predict
    2025 rows it never trained on.
    """
    rows = []
    for season in (2024, 2025):
        for i in range(30):
            yards = 100.0 + i * 5.0
            rows.append(
                {
                    "position": "QB",
                    "season": season,
                    "season_type": "regularseason",
                    "did_not_play": False,
                    "box_value": 0.01 * yards + 0.05,
                    "stat_31": yards,
                }
            )
    return rows


def test_fit_position_model_recovers_linear_relationship() -> None:
    rows = _synthetic_rows()
    model = fit_position_model(rows, position="QB", train_season=2024, test_season=2025)
    assert model is not None
    assert model.test_rows == 30
    assert model.test_r2 > 0.999
    assert model.test_mae < 0.01
    # Recovered coefficient on stat_31 should be close to the true 0.01.
    idx = model.feature_names.index("stat_31")
    assert abs(model.coefficients[idx + 1] - 0.01) < 1e-3


def test_fit_position_model_returns_none_below_minimum_rows() -> None:
    rows = [
        {
            "position": "QB",
            "season": 2024,
            "season_type": "regularseason",
            "did_not_play": False,
            "box_value": 1.0,
            "stat_31": 100.0,
        }
    ]
    assert fit_position_model(rows, position="QB", train_season=2024, test_season=2025) is None


def test_fit_position_model_excludes_preseason_and_dnp() -> None:
    rows = _synthetic_rows()
    rows.append(
        {
            "position": "QB",
            "season": 2024,
            "season_type": "preseason",
            "did_not_play": False,
            "box_value": 999.0,
            "stat_31": 1.0,
        }
    )
    rows.append(
        {
            "position": "QB",
            "season": 2024,
            "season_type": "regularseason",
            "did_not_play": True,
            "box_value": 999.0,
            "stat_31": 1.0,
        }
    )
    model = fit_position_model(rows, position="QB", train_season=2024, test_season=2025)
    assert model is not None
    assert model.train_rows == 30  # the two poisoned rows must not have leaked in


def test_fit_all_and_predict(tmp_path: Path) -> None:
    dataset = tmp_path / "box_stats.jsonl"
    with dataset.open("w", encoding="utf-8") as fh:
        for row in _synthetic_rows():
            fh.write(json.dumps(row) + "\n")
    bundle = fit_all(dataset)
    assert "QB" in bundle.models
    predicted = bundle.predict("QB", {"stat_31": 300.0})
    assert predicted is not None
    assert abs(predicted - (0.01 * 300.0 + 0.05)) < 0.01
    assert bundle.predict("K", {}) is None


def test_bundle_json_roundtrip(tmp_path: Path) -> None:
    rows = _synthetic_rows()
    bundle = fit_position_model(rows, position="QB", train_season=2024, test_season=2025)
    assert bundle is not None
    from nfl_oracle.valuelaw.model import ValueModelBundle

    wrapped = ValueModelBundle(models={"QB": bundle}, dataset_row_count=60, dataset_sha256=None)
    payload = bundle_to_json(wrapped)
    restored = bundle_from_json(payload)
    assert restored.models["QB"].coefficients == wrapped.models["QB"].coefficients

    path = tmp_path / "value_model.json"
    write_bundle(wrapped, path)
    reloaded = load_bundle(path)
    assert reloaded.models["QB"].test_r2 == wrapped.models["QB"].test_r2
