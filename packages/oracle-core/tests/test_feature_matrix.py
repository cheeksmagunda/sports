"""Portfolio FEATURE_MATRIX vocabulary and freeze wiring (#583)."""

from __future__ import annotations

from oracle_core.feature_matrix import (
    FEATURE_MATRIX,
    feature_matrix,
    matrix_document,
    unused_gold,
    wire_available_to_freeze,
)


def test_matrix_has_available_wired_serving_columns() -> None:
    rows = feature_matrix()
    assert len(rows) == len(FEATURE_MATRIX)
    assert len(rows) >= 12
    for row in rows:
        for column in ("available", "wired", "serving"):
            assert row[column] in {
                "yes",
                "no",
                "partial",
                "leakage_blocked",
                "label_only",
            }
        assert row["serve"] in {"on", "off"}


def test_unused_gold_excludes_production_on_signals() -> None:
    gold = {row["feature"] for row in unused_gold()}
    assert any("prop_points" in name for name in gold)
    assert any("popularPlayers" in name or "mostCommon" in name for name in gold)
    assert any("previousMeetings" in name for name in gold)
    assert not any("moneyline" in name for name in gold)
    assert not any("seasonAverages" in name for name in gold)


def test_wire_copies_moneyline_and_season_averages_when_present() -> None:
    wired = wire_available_to_freeze(
        "wnba",
        {
            "team_moneyline": -140,
            "opponent_moneyline": 120,
            "moneyline_available": 1,
            "overall_rank": 12,
            "season_averages": {"pts": 15.2, "reb": 5, "note": "skip"},
            "base_boosted_value": 99.0,
        },
    )
    assert wired["team_moneyline"] == -140.0
    assert wired["opponent_moneyline"] == 120.0
    assert wired["moneyline_available"] == 1.0
    assert wired["overall_rank"] == 12.0
    assert wired["season_avg_pts"] == 15.2
    assert wired["season_avg_reb"] == 5.0
    assert "base_boosted_value" not in wired
    assert "note" not in wired


def test_wire_records_missing_moneyline_without_inventing_prices() -> None:
    wired = wire_available_to_freeze(
        "wnba",
        {
            "moneyline_available": 0,
            "team_moneyline": -150,
            "season_averages": None,
        },
    )
    assert wired == {"moneyline_available": 0.0}


def test_wire_off_rows_do_not_leak_into_nfl() -> None:
    wired = wire_available_to_freeze(
        "nfl",
        {
            "moneyline_available": 1,
            "team_moneyline": -110,
            "opponent_moneyline": -110,
            "previous_meetings": 3,
        },
    )
    assert wired["team_moneyline"] == -110.0
    assert "previous_meetings" not in wired


def test_matrix_document_round_trip_shape() -> None:
    doc = matrix_document()
    assert doc["schema_version"] == 1
    assert doc["issue"] == 583
    assert len(doc["unused_gold"]) >= 3
    assert any(row["serve"] == "on" for row in doc["features"])


def test_sport_filter_wnba() -> None:
    wnba = feature_matrix(sport="wnba")
    assert wnba
    assert all("wnba" in row["sports"] for row in wnba)
