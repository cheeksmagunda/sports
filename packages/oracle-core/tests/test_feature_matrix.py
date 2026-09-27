"""Portfolio FEATURE_MATRIX vocabulary (#583)."""

from __future__ import annotations

from oracle_core.feature_matrix import (
    FEATURE_MATRIX,
    feature_matrix,
    matrix_document,
    unused_gold,
)


def test_matrix_has_available_wired_serving_columns() -> None:
    rows = feature_matrix()
    assert len(rows) == len(FEATURE_MATRIX)
    assert len(rows) >= 12
    for row in rows:
        assert row["available"] in {
            "yes",
            "no",
            "partial",
            "leakage_blocked",
            "label_only",
        }
        assert row["wired"] in {"yes", "no", "partial", "leakage_blocked", "label_only"}
        assert row["serving"] in {
            "yes",
            "no",
            "partial",
            "leakage_blocked",
            "label_only",
        }


def test_unused_gold_lists_high_value_gaps() -> None:
    gold = {row["feature"] for row in unused_gold()}
    assert any("prop_points" in name for name in gold)
    assert any("moneyline" in name for name in gold)
    assert any("seasonAverages" in name for name in gold)
    assert any("popularPlayers" in name or "mostCommon" in name for name in gold)


def test_matrix_document_round_trip_shape() -> None:
    doc = matrix_document()
    assert doc["schema_version"] == 1
    assert doc["issue"] == 583
    assert "unused_gold" in doc
    assert len(doc["unused_gold"]) >= 5


def test_sport_filter_wnba() -> None:
    wnba = feature_matrix(sport="wnba")
    assert wnba
    assert all("wnba" in row["sports"] for row in wnba)
