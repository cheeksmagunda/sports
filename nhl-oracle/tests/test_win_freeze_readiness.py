"""T-40 win freeze: complete pool, zero boost until every team has played."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nhl_oracle.contest.pick import select_five_player_pick
from nhl_oracle.contract.boost_gate import NHL_EXPECTED_TEAM_COUNT
from nhl_oracle.contract.schema import BoostRegime, NhlCandidate, NhlContestContract
from nhl_oracle.scheduler.readiness import (
    empty_snapshot_readiness,
    evaluate_win_freeze_readiness,
)
from nhl_oracle.scheduler.t40 import evaluate_freeze_coherence

LOCK = datetime(2026, 9, 29, 21, 0, tzinfo=UTC)
INSIDE = LOCK - timedelta(minutes=20)
BEFORE = LOCK - timedelta(minutes=50)
CAPTURED = "2026-09-29T20:00:00+00:00"


def _candidates(n: int) -> tuple[NhlCandidate, ...]:
    return tuple(
        NhlCandidate(
            player_id=i,
            position="C" if i % 5 else "G",
            score_value=float(n - i),
            captured_at=CAPTURED,
        )
        for i in range(1, n + 1)
    )


def _values(candidates: tuple[NhlCandidate, ...]) -> dict[int, float]:
    return {c.player_id: float(c.score_value or 0.0) for c in candidates}


def _partial_coverage() -> dict[str, int]:
    coverage = {f"T{i:02d}": 1 for i in range(NHL_EXPECTED_TEAM_COUNT)}
    coverage["T00"] = 0
    return coverage


def test_empty_snapshot_does_not_invent_a_five() -> None:
    report = empty_snapshot_readiness()
    assert report.freeze_ready is False
    assert report.pick_player_ids is None
    assert report.zero_boost_active is True
    assert report.boost_multiplier == 0.0
    assert report.contest_entry is False
    assert report.blocked_reasons == ("no_live_slate_snapshot",)


def test_incomplete_pool_does_not_emit_a_five() -> None:
    candidates = _candidates(5)
    report = evaluate_win_freeze_readiness(
        candidates=candidates,
        expected_pool_size=12,
        games_scheduled=2,
        games_captured=2,
        projected_values=_values(candidates),
        now=INSIDE,
        lock_at=LOCK,
        team_games_played=_partial_coverage(),
        card_boosts={1: 0.5},
    )
    assert report.freeze_ready is False
    assert report.pool_complete is False
    assert report.pick_player_ids is None
    assert "pool_completeness" in report.blocked_reasons
    assert report.contest_entry is False


def test_missing_game_capture_blocks_freeze() -> None:
    candidates = _candidates(6)
    report = evaluate_win_freeze_readiness(
        candidates=candidates,
        expected_pool_size=6,
        games_scheduled=2,
        games_captured=1,
        projected_values=_values(candidates),
        now=INSIDE,
        lock_at=LOCK,
        team_games_played=None,
    )
    assert report.pool_complete is False
    assert report.freeze_ready is False
    assert report.pick_player_ids is None
    assert report.zero_boost_active is True


def test_complete_pool_inside_t40_freezes_value_order_at_zero_boost() -> None:
    candidates = _candidates(8)
    report = evaluate_win_freeze_readiness(
        candidates=candidates,
        expected_pool_size=8,
        games_scheduled=2,
        games_captured=2,
        projected_values=_values(candidates),
        now=INSIDE,
        lock_at=LOCK,
        contract=NhlContestContract(boost_regime=BoostRegime.FLAT),
        team_games_played=_partial_coverage(),
        card_boosts={8: 9.0, 1: 0.4},
    )
    assert report.pool_complete is True
    assert report.zero_boost_active is True
    assert report.boost_multiplier == 0.0
    assert report.in_t40_window is True
    assert report.freeze_ready is True
    # Highest pregame value is player 1 (score n-i). Boosts must not reorder.
    assert report.pick_player_ids == (1, 2, 3, 4, 5)
    assert report.blocked_reasons == ()
    assert report.contest_entry is False


def test_complete_pool_before_t40_is_not_a_freeze() -> None:
    candidates = _candidates(8)
    report = evaluate_win_freeze_readiness(
        candidates=candidates,
        expected_pool_size=8,
        games_scheduled=2,
        games_captured=2,
        projected_values=_values(candidates),
        now=BEFORE,
        lock_at=LOCK,
        team_games_played=_partial_coverage(),
    )
    assert report.pool_complete is True
    assert report.pick_player_ids == (1, 2, 3, 4, 5)
    assert report.freeze_ready is False
    assert "before_t40_window" in report.blocked_reasons


def test_missing_projection_blocks_even_when_pool_is_complete() -> None:
    candidates = _candidates(6)
    values = _values(candidates)
    del values[6]
    report = evaluate_win_freeze_readiness(
        candidates=candidates,
        expected_pool_size=6,
        games_scheduled=1,
        games_captured=1,
        projected_values=values,
        now=INSIDE,
        lock_at=LOCK,
        team_games_played=_partial_coverage(),
    )
    assert report.pool_complete is True
    assert report.freeze_ready is False
    assert report.pick_player_ids is None
    assert any(reason.startswith("missing_projection_for_") for reason in report.blocked_reasons)


def test_nonzero_effective_boost_is_incoherent_while_gate_closed() -> None:
    pick = select_five_player_pick(
        {1: 5.0, 2: 4.0, 3: 3.0, 4: 2.0, 5: 1.0},
        card_boosts={1: 0.4},
        boost_multiplier=1.0,
    )
    coherence = evaluate_freeze_coherence(
        pick=pick,
        contract=NhlContestContract(),
        now=INSIDE,
        lock_at=LOCK,
    )
    assert coherence.ok is False
    assert "zero_boost_not_applied" in coherence.reasons
    assert "effective_boost_nonzero_while_gated" in coherence.reasons


def test_cleared_gate_allows_boost_once_every_team_has_played() -> None:
    played = {f"T{i:02d}": 1 for i in range(NHL_EXPECTED_TEAM_COUNT)}
    candidates = _candidates(6)
    report = evaluate_win_freeze_readiness(
        candidates=candidates,
        expected_pool_size=6,
        games_scheduled=1,
        games_captured=1,
        projected_values=_values(candidates),
        now=INSIDE,
        lock_at=LOCK,
        contract=NhlContestContract(boost_regime=BoostRegime.FLAT),
        team_games_played=played,
        card_boosts={1: 0.25},
    )
    assert report.zero_boost_active is False
    assert report.boost_multiplier == 1.0
    assert report.freeze_ready is True
    assert report.pick_player_ids == (1, 2, 3, 4, 5)


def test_naive_clock_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone_aware"):
        evaluate_win_freeze_readiness(
            candidates=_candidates(5),
            expected_pool_size=5,
            games_scheduled=1,
            games_captured=1,
            projected_values={1: 1, 2: 1, 3: 1, 4: 1, 5: 1},
            now=datetime(2026, 9, 29, 20, 0),
            lock_at=LOCK,
        )
