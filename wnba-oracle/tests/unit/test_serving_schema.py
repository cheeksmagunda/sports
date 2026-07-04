"""Serve-time enrichment schema validator (features/serving_schema.py)."""

from __future__ import annotations

import json

from wnba_oracle.features.serving_schema import (
    SchemaFinding,
    _flatten_enrichment,
    validate_enrichment,
)


def _row(pid: int = 1, position: str = "G", card_boost: float = 1.0, **f_extra) -> dict:
    features = {
        "vegas_total": 205.0,
        "is_out": 0,
        "is_starter": 1,
        "rotowire_confirmed": 1,
        "recent_minutes": 28.0,
        "per_min_rate": 0.10,
        "head_features": {"minutes_l10": 28.0},
        **f_extra,
    }
    return {
        "real_sports_player_id": pid,
        "team": "IND",
        "opponent": "LVA",
        "position": position,
        "card_boost": card_boost,
        "features_json": features,
    }


def test_healthy_pool_produces_no_findings() -> None:
    rows = [_row(pid=i, position="G" if i % 2 else "F") for i in range(1, 21)]
    assert validate_enrichment(rows) == []


def test_position_collapsed_flags_when_pool_all_G() -> None:
    rows = [_row(pid=i, position="G") for i in range(1, 15)]
    findings = validate_enrichment(rows)
    triggers = [f.trigger for f in findings]
    assert "schema_position_collapsed" in triggers


def test_position_collapsed_silent_below_threshold() -> None:
    rows = [_row(pid=i, position="G") for i in range(1, 5)]
    findings = validate_enrichment(rows)
    assert [f.trigger for f in findings] == []


def test_card_boost_out_of_range_flags() -> None:
    rows = [
        _row(pid=1, card_boost=1.0),
        _row(pid=2, card_boost=-0.5),
        _row(pid=3, card_boost=6.0),
    ] + [_row(pid=10 + i, position="F") for i in range(20)]
    findings = validate_enrichment(rows)
    triggers = [f.trigger for f in findings]
    assert "schema_card_boost_out_of_range" in triggers
    bad = next(f for f in findings if f.trigger == "schema_card_boost_out_of_range")
    assert bad.payload["n_bad"] == 2


def test_minutes_feed_sparse_flags() -> None:
    rows = [
        _row(pid=i, position="G" if i % 2 else "F", recent_minutes=None, per_min_rate=None)
        for i in range(1, 15)
    ]
    findings = validate_enrichment(rows)
    triggers = [f.trigger for f in findings]
    assert "schema_minutes_feed_sparse" in triggers


def test_head_features_sparse_flags() -> None:
    rows = [_row(pid=i, position="G" if i % 2 else "F", head_features=None) for i in range(1, 15)]
    findings = validate_enrichment(rows)
    triggers = [f.trigger for f in findings]
    assert "schema_head_features_sparse" in triggers


def test_prop_prob_out_of_range_flags() -> None:
    rows = [_row(pid=1, position="G", prop_points_over_prob=1.5)]
    rows.extend(_row(pid=i, position="F") for i in range(2, 15))
    findings = validate_enrichment(rows)
    triggers = [f.trigger for f in findings]
    assert "schema_prop_prob_out_of_range" in triggers


def test_vegas_partial_gap_flags() -> None:
    rows = [_row(pid=i, position="G" if i % 2 else "F") for i in range(1, 11)]
    # 2 out of 10 rows have vegas_total=0 -> above the 10% floor, under 100%
    rows[0]["features_json"]["vegas_total"] = 0.0
    rows[1]["features_json"]["vegas_total"] = 0.0
    triggers = [f.trigger for f in validate_enrichment(rows)]
    assert "schema_vegas_partial_gap" in triggers


def test_strict_raises_on_finding() -> None:
    rows = [_row(pid=1, card_boost=99.0)]
    rows.extend(_row(pid=i, position="F") for i in range(2, 15))
    try:
        validate_enrichment(rows, strict=True)
    except ValueError as exc:
        assert "schema_card_boost_out_of_range" in str(exc)
    else:
        raise AssertionError("strict=True must raise on findings")


def test_flatten_handles_string_features_json() -> None:
    row = _row(pid=42)
    row["features_json"] = json.dumps(row["features_json"])
    flat = _flatten_enrichment([row])
    assert flat[0]["player_id"] == 42
    assert flat[0]["is_starter"] == 1


def test_empty_pool_returns_no_findings() -> None:
    assert validate_enrichment([]) == []


def test_finding_payload_carries_context() -> None:
    rows = [_row(pid=i, position="G") for i in range(1, 15)]
    findings = validate_enrichment(rows)
    collapsed = next(f for f in findings if f.trigger == "schema_position_collapsed")
    assert isinstance(collapsed, SchemaFinding)
    assert collapsed.payload["distinct_positions"] == ["G"]
    assert collapsed.payload["n_rows"] == 14
