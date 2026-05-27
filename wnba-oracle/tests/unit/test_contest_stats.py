"""Unit tests for contest_stats parsing."""

from __future__ import annotations

from wnba_oracle.ingest.contest_stats import (
    ContestLabel,
    _parse_drafts,
    _parse_real_score,
    dedupe_by_player,
)


def test_parse_drafts() -> None:
    assert _parse_drafts(None) is None
    assert _parse_drafts(7) == 7
    assert _parse_drafts("42") == 42
    assert _parse_drafts("1.1k") == 1100
    assert _parse_drafts("") is None
    assert _parse_drafts("nope") is None


def test_parse_real_score() -> None:
    assert _parse_real_score(None) is None
    assert _parse_real_score("7.24826") == 7.24826
    assert _parse_real_score("-0.45") == -0.45
    assert _parse_real_score("+1.2") == 1.2
    assert _parse_real_score("") is None
    assert _parse_real_score("nan-ish") is None


def test_dedupe_by_player_keeps_first() -> None:
    labels = [
        ContestLabel(
            contest_id=1, slate_date="2026-05-26", section="highestBoostedValuePlayers",
            platform_player_id=42, display_name="X", team_key="LVA",
            card_boost=1.5, drafts=100, real_score=5.0,
        ),
        ContestLabel(
            contest_id=1, slate_date="2026-05-26", section="popularPlayers",
            platform_player_id=42, display_name="X", team_key="LVA",
            card_boost=1.5, drafts=200, real_score=5.0,
        ),
        ContestLabel(
            contest_id=1, slate_date="2026-05-26", section="popularPlayers",
            platform_player_id=43, display_name="Y", team_key="NYL",
            card_boost=0.5, drafts=300, real_score=3.0,
        ),
    ]
    out = dedupe_by_player(labels)
    assert len(out) == 2
    assert out[0].platform_player_id == 42
    assert out[0].section == "highestBoostedValuePlayers"  # first wins
    assert out[1].platform_player_id == 43
