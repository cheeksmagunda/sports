"""Tests for Real value label schema + Corpus G extraction."""

from __future__ import annotations

from pathlib import Path

from nfl_oracle.labels import (
    ValueLabel,
    is_live_feature_allowed,
    is_train_label_row,
    labels_from_stats_payload,
    load_labels_from_corpus_root,
    schema_document,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "value_labels"


def test_schema_document_has_clock_and_blacklist_contract() -> None:
    doc = schema_document()
    assert doc["target"] == "value"
    assert doc["observation_only"] is True
    assert doc["live"]["contest_entry"] is False
    assert "same_slate_final_value" in doc["live"]["blacklist"]
    assert "event_time" in doc["fields"]
    assert "decision_at" in doc["fields"]


def test_same_slate_value_never_live_feature() -> None:
    assert is_live_feature_allowed(decision_at="2026-09-07T16:00:00Z") is False


def test_labels_from_stats_payload_skips_null_value() -> None:
    stats = {
        "playerBoxScores": [
            {"playerId": 1, "position": "qb", "value": "2.5", "teamId": 9},
            {"playerId": 2, "position": "RB", "value": None},
            {"playerId": 3, "position": "WR", "value": ""},
        ]
    }
    rows = labels_from_stats_payload(
        stats=stats,
        game_id=99,
        season=2024,
        clocks={"event_time": "2024-09-10T17:00:00Z", "decision_at": None},
    )
    assert len(rows) == 1
    assert rows[0].player_id == 1
    assert rows[0].position == "QB"
    assert rows[0].value == 2.5
    assert is_train_label_row(rows[0]) is True


def test_load_labels_from_fixture_corpus() -> None:
    labels = load_labels_from_corpus_root(FIXTURE_ROOT)
    assert len(labels) == 21
    seasons = sorted({row.season for row in labels})
    assert seasons == [2022, 2023, 2024, 2025]
    assert all(isinstance(row, ValueLabel) for row in labels)
    assert all(row.source_available_at for row in labels)
