"""Unit tests for nfl_oracle.replay.harness."""

from __future__ import annotations

from datetime import UTC, date, datetime

from nfl_oracle.contests.parse import ParsedContest
from nfl_oracle.contests.schema import ContestRecord, DraftStatRow, EntryLineupPick, EntryRecord
from nfl_oracle.replay.harness import (
    eligible_pool_values,
    hindsight_best_lineup,
    is_optimally_ordered,
    pooled_summary,
    replay_contest,
    slot_regret,
)

SLOTS = (2.0, 1.8, 1.6, 1.4, 1.2)
CAPTURED = datetime(2025, 9, 1, tzinfo=UTC)


def _contest(contest_id: int, *, boosts: dict[int, float] | None = None) -> ContestRecord:
    return ContestRecord(
        contest_id=contest_id,
        sport="nfl",
        day=date(2025, 9, 1),
        end_day=date(2025, 9, 1),
        lineup_size=5,
        slot_multipliers=SLOTS,
        entrants=1000,
        is_finalized=True,
        captured_at=CAPTURED,
    )


def _pick(player_id: int, slot: int, value: float, boost: float) -> EntryLineupPick:
    slot_mult = SLOTS[slot - 1]
    return EntryLineupPick(
        player_id=player_id,
        slot=slot,
        slot_multiplier=slot_mult,
        card_boost=boost,
        effective_multiplier=slot_mult + boost,
        value=value,
        score=value * (slot_mult + boost),
    )


def _draft_row(contest_id: int, player_id: int, value: float, boost: float) -> DraftStatRow:
    return DraftStatRow(
        contest_id=contest_id,
        player_id=player_id,
        section="Highest value",
        card_boost=boost,
        value=value,
    )


def test_hindsight_best_prefers_boosted_player_over_slightly_higher_raw_value() -> None:
    """Selection must weigh boost, not just raw value: this is the bug the DP fixes.

    Naive top-5-by-raw-value is {1, 2, 3, 4, 5}. Player 6 has slightly lower
    raw value than player 5 but carries a boost of 3.0. Including 6 in place
    of 5 raises the order-invariant sum(value * boost) term by more than it
    lowers the rearrangement term, so the true optimum swaps 5 out for 6.
    """
    pool = {
        1: (10.0, 0.0),
        2: (9.0, 0.0),
        3: (8.0, 0.0),
        4: (7.0, 0.0),
        5: (6.0, 0.0),
        6: (5.9, 3.0),
    }
    draft_stats = tuple(_draft_row(1, pid, v, b) for pid, (v, b) in pool.items())
    contest = ParsedContest(
        contest=_contest(1),
        entries=(),
        draft_stats=draft_stats,
        missing_routes=(),
        law_verified=True,
    )
    best = hindsight_best_lineup(contest)
    assert best is not None
    assert 6 in best.player_ids
    assert 5 not in best.player_ids
    naive_top5_by_value = {1, 2, 3, 4, 5}
    assert set(best.player_ids) != naive_top5_by_value


def test_hindsight_best_matches_top_by_value_when_boosts_are_uniform() -> None:
    """Zero-boost (or any uniform-boost) regime: naive top-k-by-value is exact."""
    pool = {1: 10.0, 2: 8.0, 3: 6.0, 4: 4.0, 5: 2.0, 6: 1.0}
    draft_stats = tuple(_draft_row(1, pid, v, 0.0) for pid, v in pool.items())
    contest = ParsedContest(
        contest=_contest(1),
        entries=(),
        draft_stats=draft_stats,
        missing_routes=(),
        law_verified=True,
    )
    best = hindsight_best_lineup(contest)
    assert best is not None
    assert set(best.player_ids) == {1, 2, 3, 4, 5}
    top_five = sorted(pool.values(), reverse=True)[:5]
    expected = sum(v * s for v, s in zip(top_five, SLOTS, strict=True))
    assert abs(best.total_score - expected) < 1e-9


def test_slot_regret_zero_for_descending_order_entry() -> None:
    entry = EntryRecord(
        contest_id=1,
        entry_id=1,
        rank=1,
        picks=(
            _pick(1, 1, 10.0, 0.0),
            _pick(2, 2, 8.0, 0.0),
            _pick(3, 3, 6.0, 0.0),
            _pick(4, 4, 4.0, 0.0),
            _pick(5, 5, 2.0, 0.0),
        ),
    )
    assert slot_regret(entry) == 0.0
    assert is_optimally_ordered(entry) is True


def test_slot_regret_positive_for_misordered_entry() -> None:
    entry = EntryRecord(
        contest_id=1,
        entry_id=1,
        rank=1,
        picks=(
            _pick(1, 1, 6.0, 0.0),
            _pick(2, 2, 10.0, 0.0),
            _pick(3, 3, 8.0, 0.0),
            _pick(4, 4, 4.0, 0.0),
            _pick(5, 5, 2.0, 0.0),
        ),
    )
    regret = slot_regret(entry)
    assert regret is not None and regret > 0
    assert is_optimally_ordered(entry) is False


def test_replay_contest_and_pooled_summary_end_to_end() -> None:
    values = {1: 10.0, 2: 8.0, 3: 6.0, 4: 4.0, 5: 2.0, 6: 1.0}
    draft_stats = tuple(_draft_row(1, pid, v, 0.0) for pid, v in values.items())
    winner = EntryRecord(
        contest_id=1,
        entry_id=1,
        rank=1,
        picks=(
            _pick(1, 1, 10.0, 0.0),
            _pick(2, 2, 8.0, 0.0),
            _pick(3, 3, 6.0, 0.0),
            _pick(4, 4, 4.0, 0.0),
            _pick(6, 5, 1.0, 0.0),
        ),
    )
    contest = ParsedContest(
        contest=_contest(1),
        entries=(winner,),
        draft_stats=draft_stats,
        missing_routes=(),
        law_verified=True,
    )
    result = replay_contest(contest)
    assert result.is_zero_boost is True
    assert result.hindsight_best is not None
    assert result.winner_capture_ratio is not None and 0.0 < result.winner_capture_ratio < 1.0
    assert result.entries_scored == 1
    assert result.entries_optimally_ordered == 1

    summary = pooled_summary([result])
    assert summary.n_contests == 1
    assert summary.optimal_order_rate == 1.0
    assert summary.n_capture_observed == 1


def test_eligible_pool_prefers_entry_value_over_draft_stats_value() -> None:
    draft_stats = (_draft_row(1, 1, 5.0, 0.0),)
    entry = EntryRecord(
        contest_id=1,
        entry_id=1,
        rank=1,
        picks=(
            _pick(1, 1, 5.05, 0.0),
            _pick(2, 2, 4.0, 0.0),
            _pick(3, 3, 3.0, 0.0),
            _pick(4, 4, 2.0, 0.0),
            _pick(5, 5, 1.0, 0.0),
        ),
    )
    contest = ParsedContest(
        contest=_contest(1),
        entries=(entry,),
        draft_stats=draft_stats,
        missing_routes=(),
        law_verified=True,
    )
    pool = eligible_pool_values(contest)
    assert pool[1] == 5.05
