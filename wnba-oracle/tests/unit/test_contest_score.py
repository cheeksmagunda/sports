"""Contest scoring, checked against the platform's own arithmetic.

The fixture is three real top-20 entries lifted verbatim from
``contest_leaderboards.lineup``. They are the evidence for the D42 rule, so the
tests assert against the platform's numbers rather than against our restatement
of them: if Real Sports ever changes how a lineup total is formed, these fail.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wnba_oracle.eval.contest_score import (
    DEFAULT_SLOT_BASES,
    committed_order_score,
    ev_optimal_order,
    hindsight_max_score,
    slot_order_headroom,
)

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "realsports" / "leaderboard_entries.json"
)


def _entries() -> list[dict]:
    return json.loads(FIXTURE.read_text())


def _ids(entries: list[dict]) -> list[str]:
    return [f"{e['slate_date']}#{e['rank']}" for e in entries]


ENTRIES = _entries()


@pytest.mark.parametrize("entry", ENTRIES, ids=_ids(ENTRIES))
def test_slot_bases_are_the_platform_multiplier_minus_bonus(entry: dict) -> None:
    """multiplier == slot_base[order] + multiplierBonus, for every slot."""
    for player in entry["lineup"]:
        base = float(player["multiplier"]) - float(player["multiplierBonus"])
        assert base == pytest.approx(DEFAULT_SLOT_BASES[player["order"]], abs=1e-9)


@pytest.mark.parametrize("entry", ENTRIES, ids=_ids(ENTRIES))
def test_committed_order_score_reproduces_the_platform_total(entry: dict) -> None:
    """Our scorer must land on the score the platform published for the entry.

    ``order`` is the committed slot, so values and boosts go in in that order and
    are NOT re-sorted. The platform rounds its published total to 2dp, hence the
    tolerance; the per-player scores are checked exactly below.
    """
    lineup = sorted(entry["lineup"], key=lambda p: p["order"])
    values = [float(p["value"]) for p in lineup]
    boosts = [float(p["multiplierBonus"]) for p in lineup]

    assert committed_order_score(values, boosts) == pytest.approx(
        entry["platform_score"], abs=0.005
    )


@pytest.mark.parametrize("entry", ENTRIES, ids=_ids(ENTRIES))
def test_per_player_score_is_value_times_multiplier(entry: dict) -> None:
    """The decomposition the module docstring relies on, term by term."""
    for player in entry["lineup"]:
        assert float(player["score"]) == pytest.approx(
            float(player["value"]) * float(player["multiplier"]), rel=1e-9
        )


def test_hindsight_beats_committed_when_the_order_was_wrong() -> None:
    """The whole point of keeping the two apart: they must not coincide here."""
    values = [1.0, 9.0, 1.0, 1.0, 1.0]  # the big score sits in the 1.8x slot
    boosts = [0.0] * 5

    committed = committed_order_score(values, boosts)
    hindsight = hindsight_max_score(values, boosts)

    assert hindsight > committed
    assert slot_order_headroom(values, boosts) == pytest.approx(hindsight - committed)
    # 9.0 moves from the 1.8x base to the 2.0x base; 1.0 moves the other way.
    assert hindsight - committed == pytest.approx(9.0 * 0.2 - 1.0 * 0.2)


def test_hindsight_equals_committed_when_the_order_was_already_optimal() -> None:
    values = [9.0, 5.0, 3.0, 2.0, 1.0]
    boosts = [0.0] * 5

    assert hindsight_max_score(values, boosts) == pytest.approx(
        committed_order_score(values, boosts)
    )
    assert slot_order_headroom(values, boosts) == pytest.approx(0.0)


def test_boost_term_is_invariant_to_slot_order() -> None:
    """sum(value * boost) does not depend on the pairing, so only the slot term
    can differ between two orderings. This is what makes ordering a pure
    rearrangement problem."""
    values = [4.0, 1.0, 7.0, 2.0, 3.0]
    boosts = [0.5, 2.0, 0.0, 1.0, 0.25]
    pairs = list(zip(values, boosts))
    reordered = [pairs[i] for i in (2, 0, 4, 3, 1)]

    boost_term = sum(v * b for v, b in pairs)
    reordered_boost_term = sum(v * b for v, b in reordered)
    assert boost_term == pytest.approx(reordered_boost_term)

    slot_term = committed_order_score(values, boosts) - boost_term
    reordered_slot_term = (
        committed_order_score([v for v, _ in reordered], [b for _, b in reordered])
        - reordered_boost_term
    )
    assert slot_term != pytest.approx(reordered_slot_term)


def test_ev_optimal_order_pairs_highest_expectation_with_highest_base() -> None:
    assert ev_optimal_order([1.0, 9.0, 3.0, 7.0, 5.0]) == (1, 3, 4, 2, 0)


def test_ev_optimal_order_breaks_ties_by_input_position() -> None:
    assert ev_optimal_order([2.0, 2.0, 2.0, 2.0, 2.0]) == (0, 1, 2, 3, 4)


def test_ev_optimal_order_is_the_best_achievable_under_correct_predictions() -> None:
    """If predictions were perfect, the ex-ante order would BE the hindsight
    order. That equivalence is why ev_optimal_order is the right ex-ante rule."""
    values = [3.0, 8.0, 1.0, 6.0, 4.0]
    boosts = [0.0] * 5
    order = ev_optimal_order(values)

    assert committed_order_score(
        [values[i] for i in order], [boosts[i] for i in order]
    ) == pytest.approx(hindsight_max_score(values, boosts))


@pytest.mark.parametrize(
    ("values", "boosts"),
    [
        ([1.0] * 4, [0.0] * 4),  # too few picks
        ([1.0] * 6, [0.0] * 6),  # too many picks
    ],
)
def test_wrong_lineup_size_is_rejected(values: list[float], boosts: list[float]) -> None:
    with pytest.raises(ValueError, match="expected 5 picks"):
        committed_order_score(values, boosts)


def test_mismatched_values_and_boosts_are_rejected() -> None:
    with pytest.raises(ValueError, match="length mismatch"):
        committed_order_score([1.0] * 5, [0.0] * 4)
