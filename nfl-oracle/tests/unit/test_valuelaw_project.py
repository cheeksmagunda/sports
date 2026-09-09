from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nfl_oracle.recommendations.schema import Candidate, EvidenceClock
from nfl_oracle.valuelaw.candidates import CandidateRow, PlayerHistory
from nfl_oracle.valuelaw.project import ewma, project_candidates, recommend_slots

NOW = datetime(2026, 9, 9, 20, tzinfo=UTC)


def _candidate(player_id: int, *, status: str | None = "Active") -> Candidate:
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
        card_boost=0.0,
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


def test_project_candidates_and_zero_boost_slot_order() -> None:
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


def test_out_player_is_zeroed_and_boosted_slate_refuses_zero_boost_helper() -> None:
    rows = (
        CandidateRow(candidate=_candidate(1, status="Out"), history=_history(1, (9.0, 9.0, 9.0))),
        *tuple(
            CandidateRow(candidate=_candidate(i), history=_history(i, (float(i),) * 3))
            for i in range(2, 7)
        ),
    )
    projected = project_candidates(rows)
    assert next(item for item in projected if item.player_id == 1).projected_value == 0.0
    boosted = projected[1].__class__(**{**projected[1].__dict__, "card_boost": 0.5})
    with pytest.raises(ValueError, match="zero_boost"):
        recommend_slots((projected[0], boosted, *projected[2:]))
