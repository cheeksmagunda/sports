"""Tests for train/live Corpus G clock helpers."""

from __future__ import annotations

from nfl_oracle.ingest.clocks import (
    clock_field_docs,
    clocks_for_game,
    event_time_from_game,
    source_available_at_from_game,
)


def test_event_and_source_available_prefer_finalization_clocks() -> None:
    game = {
        "dateTime": "2024-11-03T18:00:00.000Z",
        "day": "2024-11-03",
        "postProcessedAt": "2024-11-03T21:25:31.277Z",
        "gameEndDateTime": "2024-11-03T21:08:59.351Z",
        "closedAt": "2024-11-03T21:08:59.351Z",
    }
    assert event_time_from_game(game) == "2024-11-03T18:00:00.000Z"
    assert source_available_at_from_game(game) == "2024-11-03T21:25:31.277Z"


def test_source_available_null_when_only_kickoff_known() -> None:
    game = {"dateTime": "2002-09-08T17:04:44.000Z", "day": "2002-09-08"}
    assert event_time_from_game(game) == "2002-09-08T17:04:44.000Z"
    assert source_available_at_from_game(game) is None


def test_clocks_for_game_includes_decision_at_slot() -> None:
    clocks = clocks_for_game(
        {"dateTime": "2024-11-03T18:00:00.000Z"},
        captured_at="2026-09-06T01:00:00Z",
        decision_at=None,
    )
    assert clocks["captured_at"] == "2026-09-06T01:00:00Z"
    assert clocks["decision_at"] is None
    docs = clock_field_docs()
    assert "event_time" in docs and "decision_at" in docs
