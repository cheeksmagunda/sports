"""WNBA RS field matrix (#523 / #526)."""

from __future__ import annotations

from wnba_oracle.features.rs_field_map import mapped_rs_field_count, rs_field_matrix


def test_wnba_rs_field_matrix() -> None:
    rows = rs_field_matrix()
    assert mapped_rs_field_count() >= 5
    statuses = {r["status"] for r in rows}
    assert "mapped" in statuses
    assert "label" in statuses
    assert "leakage-blocked" in statuses
    vegas = next(r for r in rows if "vegas_total" in r["rs_field"])
    assert vegas["status"] == "mapped"
