"""Pin the WNBA Real Sports slot multiplier scheme.

Verified empirically against the 16-slate leaderboards corpus
(2026-05-08..2026-05-25): every single one of the 320 top-20 entries used
exactly the same set of 5 base slot multipliers. The platform fixes them
and the user only picks which player goes in which slot. Card boost is
additive on top of the slot multiplier (effective_mult = slot + boost).
"""
from __future__ import annotations

import numpy as np

from wnba_oracle.picker.optimize import DEFAULT_SLOT_MULTIPLIERS, MAX_SLOT_MULT
from wnba_oracle.picker.sample import lineup_score_samples


def test_slot_multipliers_match_real_sports_wnba() -> None:
    expected = np.array([2.0, 1.8, 1.6, 1.4, 1.2])
    np.testing.assert_array_equal(DEFAULT_SLOT_MULTIPLIERS, expected)
    # Descending order (rearrangement inequality precondition)
    diffs = np.diff(DEFAULT_SLOT_MULTIPLIERS)
    assert (diffs < 0).all(), "slot multipliers must be strictly descending"
    # Sum is exactly 8.0 (the "default" lineup floor we see in 12.5% of
    # entries — users who never touched the multiplier UI)
    assert float(DEFAULT_SLOT_MULTIPLIERS.sum()) == 8.0
    assert MAX_SLOT_MULT == 2.0


def test_lineup_score_additive_formula() -> None:
    """Verify (slot + boost) * value, not slot * (1 + boost) * value."""
    # Single sample, 5 players, all value=1, varying boost
    n_samples = 1
    n_players = 5
    real_score_samples = np.ones((n_samples, n_players))
    boosts = np.array([3.0, 0.0, 1.5, 2.0, 0.5])
    slot_multipliers = DEFAULT_SLOT_MULTIPLIERS  # [2.0, 1.8, 1.6, 1.4, 1.2]
    indices = list(range(n_players))
    out = lineup_score_samples(real_score_samples, boosts, indices, slot_multipliers)
    # By rearrangement on value (all equal), the assignment is by argsort.
    # With ties, numpy argsort gives stable order. But the SUM should be
    # invariant of permutation when values are equal:
    # sum((slot_i + boost_perm(i)) * 1) = sum(slot) + sum(boost)
    expected = float(slot_multipliers.sum() + boosts.sum())
    assert abs(out[0] - expected) < 1e-9


def test_lineup_score_rearrangement_maximizes_score() -> None:
    """Highest predicted value goes in the 2.0x slot."""
    real_score_samples = np.array([[5.0, 1.0, 3.0, 2.0, 4.0]])  # values
    boosts = np.array([0.0, 0.0, 0.0, 0.0, 0.0])  # no boosts to isolate slot effect
    indices = [0, 1, 2, 3, 4]
    out = lineup_score_samples(
        real_score_samples, boosts, indices, DEFAULT_SLOT_MULTIPLIERS
    )
    # Sorted values descending: 5, 4, 3, 2, 1
    # Slot multipliers: 2.0, 1.8, 1.6, 1.4, 1.2
    # Score: 5*2.0 + 4*1.8 + 3*1.6 + 2*1.4 + 1*1.2 = 10 + 7.2 + 4.8 + 2.8 + 1.2 = 26.0
    assert abs(out[0] - 26.0) < 1e-9


def test_lineup_score_card_boost_amplifies_value() -> None:
    """A high-boost player contributes more per slot than a low-boost one
    at the same predicted value — encoding the platform's balancing
    mechanic (low-popularity players get a boost handicap)."""
    real_score_samples = np.array([[2.0, 2.0, 2.0, 2.0, 2.0]])  # all equal
    boosts_low = np.zeros(5)
    boosts_high = np.array([3.0, 0.0, 0.0, 0.0, 0.0])  # boost only on slot 2.0
    indices = [0, 1, 2, 3, 4]
    out_low = lineup_score_samples(
        real_score_samples, boosts_low, indices, DEFAULT_SLOT_MULTIPLIERS
    )
    out_high = lineup_score_samples(
        real_score_samples, boosts_high, indices, DEFAULT_SLOT_MULTIPLIERS
    )
    # Difference = 3.0 (boost) * 2.0 (value) = 6.0
    assert abs((out_high[0] - out_low[0]) - 6.0) < 1e-9
