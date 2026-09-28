"""FEATURE_MATRIX serve-on copy into NFL context vectors (#583)."""

from __future__ import annotations

from nfl_oracle.features.matrix_wire import apply_feature_matrix
from nfl_oracle.features.rs_field_map import rs_field_matrix


def test_apply_feature_matrix_adds_season_averages_and_keeps_moneyline() -> None:
    vector = {
        "team_moneyline": -110.0,
        "opponent_moneyline": -110.0,
        "moneyline_available": 1.0,
        "overall_rank": 8.0,
    }
    apply_feature_matrix(vector, season_averages={"passYds": 265.5, "note": "x"})
    assert vector["team_moneyline"] == -110.0
    assert vector["season_avg_passyds"] == 265.5
    assert "note" not in vector
    assert "base_boosted_value" not in vector


def test_apply_feature_matrix_does_not_invent_prices_when_flag_is_zero() -> None:
    vector = {"moneyline_available": 0.0, "team_moneyline": -150.0}
    apply_feature_matrix(vector, season_averages=None)
    assert vector["moneyline_available"] == 0.0
    # Existing extractor value stays; the matrix does not add a new price key
    # when the flag is off, and it does not delete keys it skips.
    assert vector["team_moneyline"] == -150.0


def test_season_averages_row_is_mapped() -> None:
    rows = rs_field_matrix()
    season = next(row for row in rows if "seasonAverages" in row["rs_field"])
    assert season["status"] == "mapped"
