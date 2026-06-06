"""Unit coverage for the RESULTS.md auto-finalize path.

The DB layer is exercised by integration; these cover the pure scoring,
placement, and ledger-insertion logic that decide what gets written.
"""
from __future__ import annotations

import pytest

from wnba_oracle.scheduler.results_ledger import (
    AUTO_MARKER,
    PlayerLine,
    SlateResult,
    build_player_lines,
    insert_entry,
    position_summary,
    render_entry,
    slate_already_logged,
)

# A frozen-lineup JSONB payload shaped like job2._freeze writes it.
LINEUP_JSON = {
    "player_ids": [101, 102, 103, 104, 105],
    "slot_multipliers": [2.0, 1.8, 1.6, 1.4, 1.2],
    "per_player": [
        {"player_id": 101, "display_name": "M. Siegrist", "team": "DAL", "card_boost": 1.5},
        {"player_id": 102, "display_name": "C. Zandalasini", "team": "GSV", "card_boost": 0.7},
        {"player_id": 103, "display_name": "C. Parker-Tyus", "team": "ATL", "card_boost": 0.9},
        {"player_id": 104, "display_name": "R. Johnson", "team": "IND", "card_boost": 0.4},
        {"player_id": 105, "display_name": "G. VanSlooten", "team": "GSV", "card_boost": 0.2},
    ],
}


def test_realized_scoring_formula() -> None:
    # (slot_mult + card_boost) * real_score, summed.
    real = {101: 3.0, 102: 1.0, 103: 2.0, 104: 0.5, 105: None}
    lines = build_player_lines(LINEUP_JSON, real)
    assert lines[0].points == (2.0 + 1.5) * 3.0  # Siegrist anchor
    assert lines[2].points == (1.6 + 0.9) * 2.0  # Parker-Tyus
    assert lines[4].points == 0.0  # no label -> 0, not a crash
    assert not lines[4].played
    total = sum(p.points for p in lines)
    assert total == pytest.approx(10.5 + 2.5 + 5.0 + 0.9 + 0.0)


def test_position_summary_within_and_outside_captured() -> None:
    scores = [40.0, 30.0, 20.0]
    inside = position_summary(35.0, scores)
    assert "rank ~**2 of" in inside
    assert "gap +5.00" in inside  # winner 40 - our 35

    outside = position_summary(10.0, scores)
    assert "outside the captured top-20" in outside

    empty = position_summary(10.0, [])
    assert "No leaderboard captured" in empty


def test_render_entry_has_table_and_config() -> None:
    real = {101: 3.0, 102: None, 103: 2.0, 104: None, 105: None}
    result = SlateResult(
        slate_date="2026-05-28",
        model_sha="abc123",
        payout_regime="top_20",
        entry_recommendation="ENTER",
        expected_payout=1.234,
        players=build_player_lines(LINEUP_JSON, real),
        leaderboard_scores=[40.6, 30.0, 12.0],
    )
    entry = render_entry(result, {"CONTRARIAN_STRENGTH": 0.2, "PAYOUT_REGIME": "top_20"})
    assert "## Slate 2026-05-28 — finalized" in entry
    assert "M. Siegrist" in entry
    assert "DNP / no label" in entry  # unplayed picks flagged, not dropped
    assert "payout_regime=top_20" in entry
    assert "CONTRARIAN_STRENGTH=0.2" in entry


def test_insert_entry_lands_below_marker_newest_first() -> None:
    ledger = f"# RESULTS\n\nintro\n\n---\n\n{AUTO_MARKER}\n\n## Slate 2026-05-27 — finalized\nolder\n"
    out = insert_entry(ledger, "## Slate 2026-05-28 — finalized\nnewer\n\n")
    # Newest entry sits above the older one.
    assert out.index("2026-05-28") < out.index("2026-05-27")
    assert AUTO_MARKER in out


def test_insert_entry_without_marker_prepends_before_first_slate() -> None:
    ledger = "# RESULTS\n\n## Slate 2026-05-27 — finalized\nolder\n"
    out = insert_entry(ledger, "## Slate 2026-05-28 — finalized\nnewer\n\n")
    assert out.index("2026-05-28") < out.index("2026-05-27")


def test_slate_already_logged() -> None:
    text = "## Slate 2026-05-28 — finalized\n"
    assert slate_already_logged(text, "2026-05-28")
    assert not slate_already_logged(text, "2026-05-29")


def test_player_line_dnp_zero_value_not_played() -> None:
    line = PlayerLine(1, "X", "DAL", 0.0, 2.0, 0.0)
    assert not line.played
    assert line.points == 0.0
