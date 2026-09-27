"""Tests for durable game-stats matchup corpus append helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from oracle_core.corpus_matchup import (
    GameMatchupRecord,
    append_completed_game,
    list_appended_games,
    validate_matchup_payload,
)


def _record(**overrides: object) -> GameMatchupRecord:
    base = dict(
        sport="wnba",
        season="2026",
        game_id="1022600123",
        home_team="LVA",
        away_team="SEA",
        is_final=True,
        source="wnba_game_logs",
        captured_at="2026-09-27T12:00:00+00:00",
        game_date="2026-09-26",
        home_score=88,
        away_score=81,
        pace=96.4,
        box_lines={"home_pts": 88, "away_pts": 81},
    )
    base.update(overrides)
    return GameMatchupRecord(**base)  # type: ignore[arg-type]


def test_validate_matchup_payload_requires_core_keys() -> None:
    problems = validate_matchup_payload({"sport": "nfl"})
    assert "missing:game_id" in problems
    assert "missing:is_final" in problems


def test_append_completed_game_is_idempotent(tmp_path: Path) -> None:
    stats = {"players": [{"player_id": 1, "pts": 20}]}
    first = append_completed_game(tmp_path, matchup=_record(), stats=stats)
    assert first.wrote_matchup is True
    assert first.wrote_stats is True
    assert (first.game_dir / "matchup.json").is_file()
    assert (first.game_dir / "stats.json").is_file()
    assert (first.game_dir / "manifest.json").is_file()

    second = append_completed_game(tmp_path, matchup=_record(), stats=stats)
    assert second.wrote_matchup is False
    assert second.wrote_stats is False
    assert second.matchup_sha256 == first.matchup_sha256
    assert list_appended_games(tmp_path, sport="wnba") == [("wnba", "2026", "1022600123")]


def test_append_refuses_non_final_games(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="refusing_non_final"):
        append_completed_game(tmp_path, matchup=_record(is_final=False))
