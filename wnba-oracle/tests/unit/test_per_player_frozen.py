"""Lock the per_player JSON contract in the frozen lineup payload.

The frontend reads frozen_lineups.lineup.per_player to render the 5-card
grid (display_name, team, opponent, position, card_boost, score,
minutes interval). If the keys drift the user-facing UI silently falls
back to placeholder cards. This test pins the contract.
"""

from __future__ import annotations

from wnba_oracle.picker.optimize import LineupRecommendation
from wnba_oracle.scheduler.job2 import _build_per_player


def _proj(name: str, team: str, opp: str, pos: str, boost: float, p50: float) -> dict:
    return {
        "display_name": name,
        "team": team,
        "opponent": opp,
        "position": pos,
        "card_boost": boost,
        "pred_real_score_p50": p50,
    }


def _rec() -> LineupRecommendation:
    return LineupRecommendation(
        player_ids=(101, 202, 303, 404, 505),
        slot_multipliers=(1.5, 1.3, 1.2, 1.1, 1.0),
        lineup_score_p10=120.0,
        lineup_score_p50=180.0,
        lineup_score_p90=240.0,
        entry_flag="enter",
        expected_payout=1.4,
    )


REQUIRED_KEYS = {
    "player_id",
    "display_name",
    "team",
    "opponent",
    "position",
    "card_boost",
    "pred_real_score_p50",
    "pred_minutes_p10",
    "pred_minutes_p50",
    "pred_minutes_p90",
}


def test_per_player_emits_full_contract() -> None:
    rec = _rec()
    proj = {
        101: _proj("A. Wilson", "LVA", "NYL", "F", 0.5, 42.0),
        202: _proj("B. Stewart", "NYL", "LVA", "F", 0.3, 38.0),
        303: _proj("S. Ionescu", "NYL", "LVA", "G", 0.0, 33.0),
        404: _proj("C. Clark", "IND", "CHI", "G", 0.75, 31.0),
        505: _proj("N. Collier", "MIN", "SEA", "F", 0.2, 29.0),
    }
    out = _build_per_player(rec, proj)
    assert len(out) == 5
    for row in out:
        assert set(row.keys()) == REQUIRED_KEYS
        assert row["pred_minutes_p10"] < row["pred_minutes_p50"] < row["pred_minutes_p90"]


def test_per_player_slot_order_matches_player_ids() -> None:
    rec = _rec()
    proj = {
        101: _proj("Wilson", "LVA", "NYL", "F", 0.5, 42.0),
        202: _proj("Stewart", "NYL", "LVA", "F", 0.3, 38.0),
        303: _proj("Ionescu", "NYL", "LVA", "G", 0.0, 33.0),
        404: _proj("Clark", "IND", "CHI", "G", 0.75, 31.0),
        505: _proj("Collier", "MIN", "SEA", "F", 0.2, 29.0),
    }
    out = _build_per_player(rec, proj)
    assert [r["player_id"] for r in out] == list(rec.player_ids)
    assert [r["display_name"] for r in out] == [
        "Wilson",
        "Stewart",
        "Ionescu",
        "Clark",
        "Collier",
    ]


def test_per_player_includes_optional_game_id() -> None:
    rec = _rec()
    projections = {pid: _proj(str(pid), "LVA", "NYL", "G", 0.5, 3.0) for pid in rec.player_ids}
    projections[101]["game_id"] = "4512"

    out = _build_per_player(rec, projections)

    assert out[0]["game_id"] == "4512"
    assert all("game_id" not in row for row in out[1:])


def test_per_player_higher_slot_gets_more_minutes() -> None:
    """Rank-aware minutes default — slot 1 leans starter, slot 5 trails."""
    rec = _rec()
    proj = {pid: _proj(f"P{pid}", "T", "O", "F", 0.0, 30.0) for pid in rec.player_ids}
    out = _build_per_player(rec, proj)
    p50s = [r["pred_minutes_p50"] for r in out]
    assert p50s == sorted(p50s, reverse=True)


def test_per_player_handles_missing_projection_gracefully() -> None:
    """If a player ID is in the recommendation but not in the projection
    map (would indicate an upstream bug), the row still emits with safe
    defaults rather than crashing."""
    rec = _rec()
    proj = {101: _proj("Wilson", "LVA", "NYL", "F", 0.5, 42.0)}
    out = _build_per_player(rec, proj)
    assert len(out) == 5
    assert out[0]["display_name"] == "Wilson"
    assert out[4]["display_name"] == "Player 505"
    assert out[4]["team"] == ""


def test_per_player_passthrough_real_minutes_interval() -> None:
    """When the predictor attaches pred_minutes_p{10,50,90}, _build_per_player
    surfaces those values verbatim instead of the rank-aware fallback. This is
    the contract the frontend interval bar reads — a slot-1 role player who
    projects to 18 minutes should NOT be rendered as a 32-minute starter."""
    rec = _rec()
    proj = {
        101: {
            **_proj("Wilson", "LVA", "NYL", "F", 0.5, 42.0),
            "pred_minutes_p10": 30.0,
            "pred_minutes_p50": 33.5,
            "pred_minutes_p90": 36.5,
        },
        202: {
            **_proj("Boston", "IND", "CHI", "F", 0.3, 38.0),
            "pred_minutes_p10": 12.0,
            "pred_minutes_p50": 15.0,
            "pred_minutes_p90": 20.0,
        },
        303: _proj("Ionescu", "NYL", "LVA", "G", 0.0, 33.0),
        404: _proj("Clark", "IND", "CHI", "G", 0.75, 31.0),
        505: _proj("Collier", "MIN", "SEA", "F", 0.2, 29.0),
    }
    out = _build_per_player(rec, proj)
    assert out[0]["pred_minutes_p50"] == 33.5
    assert out[0]["pred_minutes_p10"] == 30.0
    assert out[0]["pred_minutes_p90"] == 36.5
    # A slot-2 role player projects below the slot-2 default (30.5) — real
    # data must win over the rank formula.
    assert out[1]["pred_minutes_p50"] == 15.0
    # Rows without a passed-through interval keep using the slot-aware fallback.
    assert out[2]["pred_minutes_p50"] == 29.0  # 32 - 1.5*2
