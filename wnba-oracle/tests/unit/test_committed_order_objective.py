"""The optimizer objective under committed vs per-draw slot assignment.

`lineup_score_samples` defaults to re-ranking players inside every Monte-Carlo
draw, so the highest score in that draw takes the 2.0x slot. That is
E[max over slot assignments]: an entrant fixes the order before tip and cannot
do it. `committed_order=True` fixes the order once from the per-player sample
means and scores every draw under it.

The gap matters for selection, not just for reporting: it is larger for
high-dispersion lineups, so the legacy objective systematically flatters
volatile combinations.
"""

from __future__ import annotations

import numpy as np
import pytest

from wnba_oracle.picker.optimize import OptimizeConfig
from wnba_oracle.picker.sample import lineup_score_samples

SLOTS = np.array([2.0, 1.8, 1.6, 1.4, 1.2])
NO_BOOST = np.zeros(5)
IDX = [0, 1, 2, 3, 4]


def test_defaults_to_the_legacy_per_draw_behaviour() -> None:
    """Default must stay byte-identical, so the flag is a true opt-in."""
    rng = np.random.default_rng(7)
    samples = rng.lognormal(size=(64, 5))

    assert np.array_equal(
        lineup_score_samples(samples, NO_BOOST, IDX, SLOTS),
        lineup_score_samples(samples, NO_BOOST, IDX, SLOTS, committed_order=False),
    )
    assert OptimizeConfig().committed_order_objective is False


def test_per_draw_assignment_never_scores_below_committed() -> None:
    """Re-slotting per draw can only help, so it is an upper bound everywhere."""
    rng = np.random.default_rng(11)
    samples = rng.lognormal(sigma=0.8, size=(256, 5))
    boosts = np.array([0.0, 1.0, 2.0, 0.5, 3.0])

    legacy = lineup_score_samples(samples, boosts, IDX, SLOTS)
    committed = lineup_score_samples(samples, boosts, IDX, SLOTS, committed_order=True)

    assert np.all(legacy >= committed - 1e-9)
    assert legacy.mean() > committed.mean()


def test_committed_order_uses_one_order_for_every_draw() -> None:
    """Player 4 has the highest mean, so it takes the 2.0x slot in EVERY draw --
    including the draws where it happens to score lowest."""
    samples = np.array(
        [
            [1.0, 2.0, 3.0, 4.0, 50.0],
            [1.0, 2.0, 3.0, 4.0, 0.0],  # player 4 collapses here
        ]
    )
    got = lineup_score_samples(samples, NO_BOOST, IDX, SLOTS, committed_order=True)

    # Order by mean is player 4 first, then 3, 2, 1, 0.
    # Row 0: 50*2.0 + 4*1.8 + 3*1.6 + 2*1.4 + 1*1.2 = 116.0
    # Row 1:  0*2.0 + 4*1.8 + 3*1.6 + 2*1.4 + 1*1.2 =  16.0
    assert got == pytest.approx([116.0, 16.0])

    # The legacy objective re-slots row 1, promoting player 3 to the 2.0x slot.
    legacy = lineup_score_samples(samples, NO_BOOST, IDX, SLOTS)
    assert legacy[1] == pytest.approx(4 * 2.0 + 3 * 1.8 + 2 * 1.6 + 1 * 1.4 + 0 * 1.2)
    assert legacy[1] > got[1]


def test_the_gap_grows_with_dispersion() -> None:
    """This is the selection bias, stated as a test: the legacy objective's
    overstatement is larger for the more volatile lineup, so ranking candidates
    by it tilts toward volatility."""
    rng = np.random.default_rng(3)
    steady = rng.lognormal(sigma=0.15, size=(4096, 5))
    volatile = rng.lognormal(sigma=1.20, size=(4096, 5))

    def overstatement(samples: np.ndarray) -> float:
        legacy = lineup_score_samples(samples, NO_BOOST, IDX, SLOTS)
        committed = lineup_score_samples(samples, NO_BOOST, IDX, SLOTS, committed_order=True)
        return float(legacy.mean() - committed.mean())

    assert overstatement(volatile) > overstatement(steady)


def test_boost_term_is_invariant_so_only_slots_can_differ() -> None:
    """The two conventions differ solely in the slot term. Proving the boost
    term matches is what licenses ranking on the mean as exact rather than
    heuristic."""
    rng = np.random.default_rng(5)
    samples = rng.lognormal(sigma=0.6, size=(128, 5))
    boosts = np.array([0.3, 1.7, 0.0, 2.2, 0.9])

    boost_term = samples @ boosts  # identical under any pairing
    legacy_slot_term = lineup_score_samples(samples, boosts, IDX, SLOTS) - boost_term
    committed_slot_term = (
        lineup_score_samples(samples, boosts, IDX, SLOTS, committed_order=True) - boost_term
    )

    assert np.all(legacy_slot_term >= committed_slot_term - 1e-9)


def test_committed_order_matches_an_explicit_fixed_order_computation() -> None:
    """Independent restatement of the formula, so a refactor of the vectorized
    path cannot silently change the result."""
    rng = np.random.default_rng(13)
    samples = rng.lognormal(sigma=0.5, size=(32, 5))
    boosts = np.array([1.1, 0.0, 2.5, 0.4, 1.9])

    order = np.argsort(samples.mean(axis=0), kind="stable")[::-1]
    expected = np.array(
        [sum(row[p] * (boosts[p] + SLOTS[s]) for s, p in enumerate(order)) for row in samples]
    )

    got = lineup_score_samples(samples, boosts, IDX, SLOTS, committed_order=True)
    assert got == pytest.approx(expected)
