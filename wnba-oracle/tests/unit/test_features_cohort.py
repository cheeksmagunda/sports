"""Spec / cohort assignment tests."""

from __future__ import annotations

from wnba_oracle.features.spec import (
    cohort_for_position,
    feature_columns_for_head,
)


def test_cohort_assignment() -> None:
    assert cohort_for_position("G") == "G"
    assert cohort_for_position("F") == "F"
    assert cohort_for_position("C") == "C"
    assert cohort_for_position("G-F") == "G"
    assert cohort_for_position("F-C") == "F"
    assert cohort_for_position("") == "F"
    assert cohort_for_position(None) == "F"


def test_feature_columns_for_head_includes_cohort_dvp() -> None:
    cols_g = feature_columns_for_head("minutes", "G")
    cols_f = feature_columns_for_head("minutes", "F")
    cols_c = feature_columns_for_head("minutes", "C")
    assert "opp_dvp_guard" in cols_g and "opp_dvp_forward" not in cols_g
    assert "opp_dvp_forward" in cols_f
    assert "opp_dvp_center" in cols_c
    # Base features are present in all
    for col in ("mins_l10", "card_boost", "vegas_total"):
        assert col in cols_g and col in cols_f and col in cols_c
