"""Backtest reference is Highest value boards, never winning drafts."""

from __future__ import annotations

import polars as pl

from wnba_oracle.eval.highest_value import (
    HV_SECTION,
    build_highest_value_reference,
    filter_highest_value_section,
    grade_lineup_vs_highest_value,
    rank_highest_value_players,
)


def _hv_frame() -> pl.DataFrame:
    # Mirrors operator Highest value screenshots (Copper / Flau'jae style).
    return pl.DataFrame(
        {
            "slate_date": ["2026-09-22"] * 8,
            "section": [HV_SECTION] * 7 + ["leaderboard_lineup"],
            "platform_player_id": [1, 2, 3, 4, 5, 6, 7, 99],
            "display_name": [
                "Kahleah Copper",
                "Paige Bueckers",
                "Pauline Astier",
                "Jordin Canada",
                "Alyssa Thomas",
                "Awak Kuier",
                "DeWanna Bonner",
                "Winner Draft Only",
            ],
            "team_key": ["CHI", "DAL", "CONN", "ATL", "PHX", "CONN", "CONN", "XXX"],
            "real_score": [5.3, 6.1, 3.7, 4.8, 5.2, 2.8, 3.5, 9.9],
            "card_boost": [0.5, 0.1, 1.3, 0.5, 0.2, 2.0, 1.0, 0.0],
            "drafts": [30, 1600, 96, 112, 402, 112, 118, 1],
        }
    )


def test_filter_drops_winning_draft_section() -> None:
    hv = filter_highest_value_section(_hv_frame())
    assert hv.height == 7
    assert set(hv["section"].unique().to_list()) == {HV_SECTION}


def test_rank_matches_screenshot_value_column() -> None:
    rows = list(filter_highest_value_section(_hv_frame()).iter_rows(named=True))
    ranked = rank_highest_value_players(rows)
    assert ranked[0].display_name == "Kahleah Copper"
    assert round(ranked[0].approx_total_value, 1) == 13.2
    assert ranked[1].display_name == "Paige Bueckers"
    assert round(ranked[1].approx_total_value, 1) == 12.8


def test_zero_boost_value_is_double_base() -> None:
    # Derrick Henry-style zero-boost HV board: Value == 2 * real_score.
    ranked = rank_highest_value_players(
        [{"platform_player_id": 1, "real_score": 8.1, "card_boost": 0.0, "display_name": "Henry"}]
    )
    assert round(ranked[0].approx_total_value, 1) == 16.2


def test_grade_lineup_vs_hv_not_winning_draft() -> None:
    ref = build_highest_value_reference(_hv_frame(), "2026-09-22")
    assert ref is not None
    assert "Winner Draft Only" not in {p.display_name for p in ref.players}
    grade = grade_lineup_vs_highest_value(ref.top5_player_ids, ref)
    assert grade["overlap_hv_top5"] == 5
    bad = grade_lineup_vs_highest_value((99, 10, 20, 30, 40), ref)
    assert bad["overlap_hv_top5"] == 0
