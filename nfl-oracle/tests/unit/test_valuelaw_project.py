from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nfl_oracle.recommendations.schema import Candidate, EvidenceClock
from nfl_oracle.valuelaw.candidates import CandidateRow, PlayerHistory
from nfl_oracle.valuelaw.project import ewma, project_candidates, recommend_slots

NOW = datetime(2026, 9, 9, 20, tzinfo=UTC)


def _candidate(player_id: int, *, status: str | None = "Active", boost: float = 0.0) -> Candidate:
    clock = EvidenceClock(source_available_at=NOW, captured_at=NOW)
    return Candidate(
        player_id=player_id,
        game_id=1,
        team_id=1,
        name=f"Player {player_id}",
        position="WR",
        team="SEA",
        opponent="NE",
        injury_status=status,
        card_boost=boost,
        clock=clock,
    )


def _history(player_id: int, values: tuple[float, ...]) -> PlayerHistory:
    return PlayerHistory(
        player_id=player_id,
        games=len(values),
        mean_box_value=sum(values) / len(values),
        max_box_value=max(values),
        min_box_value=min(values),
        last_box_value=values[-1],
        last_played_at=NOW - timedelta(days=1),
        seasons=(2025,),
        values=values,
    )


def test_ewma_weights_recent_values_more() -> None:
    assert ewma((1.0, 3.0), decay=0.5) == pytest.approx((3.0 + 0.5) / 1.5)


def test_out_player_is_zeroed() -> None:
    rows = (
        CandidateRow(candidate=_candidate(1, status="Out"), history=_history(1, (9.0, 9.0, 9.0))),
        *tuple(
            CandidateRow(candidate=_candidate(i), history=_history(i, (float(i),) * 3))
            for i in range(2, 7)
        ),
    )
    projected = project_candidates(rows)
    assert next(item for item in projected if item.player_id == 1).projected_value == 0.0


def test_recommend_slots_prefers_boosted_player_over_slightly_higher_raw_value() -> None:
    """Selection must weigh boost, not just raw value: mirrors the replay-harness bug fix.

    Naive top-5-by-value is {2, 3, 4, 5, 6}. Player 7 has slightly lower
    projected value than player 6 but carries a boost of 3.0. The true
    optimum swaps 6 out for 7 because the order-invariant boost term it adds
    outweighs the rearrangement term it gives up.
    """
    rows = tuple(
        CandidateRow(candidate=_candidate(pid, boost=boost), history=_history(pid, (value,) * 3))
        for pid, value, boost in [
            (2, 10.0, 0.0),
            (3, 9.0, 0.0),
            (4, 8.0, 0.0),
            (5, 7.0, 0.0),
            (6, 6.0, 0.0),
            (7, 5.9, 3.0),
        ]
    )
    projected = project_candidates(rows)
    recommendations = recommend_slots(projected)
    chosen = {item.projection.player_id for item in recommendations}
    assert 7 in chosen
    assert 6 not in chosen
    assert chosen != {2, 3, 4, 5, 6}


def test_recommend_slots_matches_descending_value_when_boosts_are_uniform() -> None:
    rows = tuple(
        CandidateRow(candidate=_candidate(player_id), history=_history(player_id, values))
        for player_id, values in {
            1: (1.0, 2.0, 3.0),
            2: (2.0, 3.0, 4.0),
            3: (3.0, 4.0, 5.0),
            4: (4.0, 5.0, 6.0),
            5: (5.0, 6.0, 7.0),
            6: (6.0, 7.0, 8.0),
        }.items()
    )
    projections = project_candidates(rows)
    recommendations = recommend_slots(projections)
    assert tuple(item.projection.player_id for item in recommendations) == (6, 5, 4, 3, 2)
    assert tuple(item.slot_multiplier for item in recommendations) == (2.0, 1.8, 1.6, 1.4, 1.2)
