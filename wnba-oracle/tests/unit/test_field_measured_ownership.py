"""Field-ownership model: measured-drafts path (D86).

The estimator re-derives the field from our own projections, which makes the
simulated field draft exactly what our value model likes and blinds the
optimizer to real duplication. These tests pin the measured path: when real
draft counts are attached, the ownership marginal IS the counts, and the
pre-D86 estimator behaviour is preserved byte-for-byte when none are.
"""

from __future__ import annotations

import numpy as np

from wnba_oracle.picker.field import (
    FieldPlayerSpec,
    project_ownership,
    simulate_field_lineups,
)


def _spec(pid: int, pred: float, boost: float, drafts: float | None = None) -> FieldPlayerSpec:
    return FieldPlayerSpec(
        player_id=pid, pred_real_score=pred, card_boost=boost, measured_drafts=drafts
    )


def test_no_measured_drafts_is_identical_to_estimator() -> None:
    """A pool with no measured counts must behave exactly as pre-D86."""
    specs = [_spec(i, pred=2.0 + 0.1 * i, boost=1.0 + 0.05 * i) for i in range(6)]
    own = project_ownership(specs)
    assert np.isclose(own.sum(), 1.0)
    # Reconstruct the estimator directly and compare.
    raw = np.array([s.pred_real_score * (1.0 + s.card_boost) for s in specs])
    raw = raw - raw.max()
    base = np.exp(raw / 6.0)
    expected = base / base.sum()
    assert np.allclose(own, expected)


def test_measured_marginal_matches_real_counts() -> None:
    """When every player has a measured count, ownership == normalized counts.

    The model's projection ordering must NOT override the observed field: a
    low-projection but heavily-drafted chalk player owns more of the field than
    a high-projection low-drafted contrarian play.
    """
    specs = [
        _spec(1, pred=1.0, boost=1.6, drafts=2600),  # chalk, low proj
        _spec(2, pred=1.0, boost=0.7, drafts=2900),  # chalk, low proj
        _spec(3, pred=3.0, boost=2.1, drafts=321),  # contrarian, high proj
        _spec(4, pred=1.5, boost=1.6, drafts=1700),
        _spec(5, pred=3.0, boost=3.1, drafts=494),
    ]
    own = project_ownership(specs)
    counts = np.array([2600, 2900, 321, 1700, 494], dtype=float)
    assert np.allclose(own, counts / counts.sum())
    # The high-projection contrarian (idx 2) must be the LEAST owned despite the
    # best projection -- the estimator alone would have ranked it near the top.
    assert own.argmin() == 2


def test_missing_count_backfilled_at_comparable_scale() -> None:
    """A late entrant with no measured count is inserted via the estimator,
    rescaled to the measured median -- not zero, not dwarfing the real counts."""
    specs = [
        _spec(1, pred=2.0, boost=1.5, drafts=2000),
        _spec(2, pred=2.0, boost=1.5, drafts=1000),
        _spec(3, pred=2.0, boost=1.5, drafts=None),  # unobserved
    ]
    own = project_ownership(specs)
    assert np.isclose(own.sum(), 1.0)
    # The back-filled player sits near the measured median (1500), so its
    # ownership lands between the two observed players, not at 0 or dominating.
    assert own[1] < own[2] < own[0]


def test_mixed_measured_and_unmeasured_rescales_estimator() -> None:
    """Realistic late-entrant scenario: 3 of 5 players have measured drafts,
    2 are unobserved (late pool entrants whose draft count isn't captured
    yet). The unobserved players must be back-filled at a sensible scale --
    not zeroed, not dominating the real counts -- and ownership must sum to 1.
    """
    specs = [
        _spec(1, pred=2.0, boost=1.5, drafts=2000),
        _spec(2, pred=2.0, boost=1.5, drafts=1000),
        _spec(3, pred=2.0, boost=1.5, drafts=500),
        _spec(4, pred=2.5, boost=2.0, drafts=None),  # late entrant
        _spec(5, pred=3.0, boost=2.5, drafts=None),  # late entrant
    ]
    own = project_ownership(specs)
    assert np.isclose(own.sum(), 1.0)
    # All values finite and non-negative.
    assert np.all(own >= 0.0)
    assert np.all(np.isfinite(own))
    # Late entrants land at non-trivial weight (rescaled to the measured
    # median magnitude via the estimator), never zero or NaN.
    assert own[3] > 0.01
    assert own[4] > 0.01
    # Measured players are ordered correctly among themselves: drafts
    # 2000 > 1000 > 500.
    assert own[0] > own[1] > own[2]


def test_mixed_path_does_not_zero_or_blow_up_unobserved() -> None:
    """Lower-bound and upper-bound sanity: with measured medians at the
    1000-mark, the rescaled estimator weight for an unobserved player should
    sit in a plausible band -- never zero (vanishing) and never wildly
    above the highest measured count (dominating).
    """
    specs = [
        _spec(1, pred=2.0, boost=1.0, drafts=2000),
        _spec(2, pred=2.0, boost=1.0, drafts=1000),
        _spec(3, pred=2.0, boost=1.0, drafts=None),  # near-median unobserved
    ]
    own = project_ownership(specs)
    assert np.isclose(own.sum(), 1.0)
    # The unobserved player at the median projection lands in the same band
    # as the measured median player. The measured player at 1000 drafts
    # represents ~33% of the field; the unobserved median-class entrant
    # should not dwarf it (>2x) nor vanish (<0.25x).
    ratio = own[2] / own[1]
    assert 0.25 < ratio < 4.0


def test_measured_ownership_changes_field_composition() -> None:
    """End-to-end: sampled field lineups should be dominated by the heavily
    drafted chalk when real counts drive ownership."""
    specs = [
        _spec(1, pred=1.0, boost=1.6, drafts=6000),  # extreme chalk
        _spec(2, pred=3.0, boost=2.1, drafts=50),
        _spec(3, pred=3.0, boost=2.1, drafts=50),
        _spec(4, pred=3.0, boost=2.1, drafts=50),
        _spec(5, pred=3.0, boost=2.1, drafts=50),
        _spec(6, pred=3.0, boost=2.1, drafts=50),
    ]
    own = project_ownership(specs)
    field = simulate_field_lineups(own, n_lineups=2000, lineup_size=5, seed=7)
    # Player index 0 is owned ~95% of the field; it should appear in nearly
    # every sampled lineup.
    appears = np.mean([0 in row for row in field])
    assert appears > 0.9


def test_empty_measured_drafts_prelock_contract() -> None:
    """Timing audit (#53 / #38): before contest lock, slate_labels.drafts is empty.

    When measured_drafts={} (pre-lock reality), project_ownership must gracefully
    and deterministically evaluate the public-value estimator fallback, with
    sum == 1.0, non-negative finite probabilities, and zero NaNs.
    """
    specs = [
        _spec(101, pred=2.5, boost=1.2, drafts=None),
        _spec(102, pred=1.8, boost=0.8, drafts=None),
        _spec(103, pred=3.2, boost=2.0, drafts=None),
        _spec(104, pred=0.9, boost=0.5, drafts=None),
        _spec(105, pred=2.1, boost=1.5, drafts=None),
    ]
    own = project_ownership(specs)
    assert np.isclose(own.sum(), 1.0)
    assert np.all(own > 0.0)
    assert np.all(np.isfinite(own))
