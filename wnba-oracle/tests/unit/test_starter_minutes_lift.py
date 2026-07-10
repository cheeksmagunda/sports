"""Minutes-conditional starter lift + mid-slot floor tilt (2026-07-10).

The lift closes the Tier-0 hole where a head-served expected starter carries
pre-promotion minutes into tonight's p50 (Kuier 07-05/07-07, Harris 07-09 --
each the slate's top missed swap). The floor tilt fades wide-interval
ceiling candidates out of the non-spike slots (Ogunbowale over Shepard,
07-07). Both are pure functions in job2_scoring; the job2 wiring is covered
by the head-path assertion at the bottom.
"""

from __future__ import annotations

import json

import pytest

from wnba_oracle.scheduler.job2_scoring import (
    _floor_tilt_multiplier,
    _starter_minutes_lift,
)


def test_lift_neutral_when_disabled() -> None:
    fj = json.dumps({"is_starter": 1, "rotowire_confirmed": 1, "recent_minutes": 15.0})
    assert _starter_minutes_lift(fj, enabled=False) == 1.0


def test_lift_neutral_for_non_starters_and_unknowns() -> None:
    bench = json.dumps({"is_starter": 0, "rotowire_confirmed": 1, "recent_minutes": 10.0})
    unknown = json.dumps({"is_starter": 0, "rotowire_confirmed": 0, "recent_minutes": 10.0})
    assert _starter_minutes_lift(bench, enabled=True) == 1.0
    assert _starter_minutes_lift(unknown, enabled=True) == 1.0


def test_lift_neutral_at_or_above_norm() -> None:
    # An established starter (minutes already at the norm) needs no correction;
    # the corpus ratio for starters with recent_minutes >= 21 is ~1.02.
    at_norm = json.dumps({"is_starter": 1, "rotowire_confirmed": 1, "recent_minutes": 25.0})
    above = json.dumps({"is_starter": 1, "rotowire_confirmed": 1, "recent_minutes": 32.0})
    assert _starter_minutes_lift(at_norm, enabled=True, norm=25.0) == 1.0
    assert _starter_minutes_lift(above, enabled=True, norm=25.0) == 1.0


def test_lift_neutral_without_minutes_history() -> None:
    # No recent_minutes feature -> Tier-3 role anchors already handle this
    # player; a ratio against zero would be unbounded.
    fj = json.dumps({"is_starter": 1, "rotowire_confirmed": 1})
    assert _starter_minutes_lift(fj, enabled=True) == 1.0


def test_lift_blends_toward_norm_kuier_row() -> None:
    # The 2026-07-07 Kuier row: expected starter (slot 5), recent_minutes
    # 18.8. blended = 0.4*18.8 + 0.6*25 = 22.52 -> lift ~1.198.
    fj = json.dumps({"is_starter": 1, "rotowire_confirmed": 0, "recent_minutes": 18.8})
    lift = _starter_minutes_lift(fj, enabled=True, norm=25.0, weight=0.6, cap=1.5)
    assert lift == pytest.approx((0.4 * 18.8 + 0.6 * 25.0) / 18.8)
    # use_expected=False restores confirmed-only gating: the expected
    # starter is no longer lifted.
    assert _starter_minutes_lift(fj, enabled=True, use_expected=False) == 1.0


def test_lift_caps_extreme_deficits() -> None:
    # A 6-minute starter would be lifted 2.9x uncapped; the cap bounds the
    # correction so a garbage-time promotion can't fabricate a star.
    fj = json.dumps({"is_starter": 1, "rotowire_confirmed": 1, "recent_minutes": 6.0})
    assert _starter_minutes_lift(fj, enabled=True, norm=25.0, weight=0.6, cap=1.5) == 1.5


def test_lift_monotone_in_minutes_deficit() -> None:
    def lift_at(rmin: float) -> float:
        fj = json.dumps({"is_starter": 1, "rotowire_confirmed": 1, "recent_minutes": rmin})
        return _starter_minutes_lift(fj, enabled=True, norm=25.0, weight=0.6, cap=1.5)

    assert lift_at(12.0) > lift_at(18.0) > lift_at(23.0) > lift_at(25.0) == 1.0


def test_floor_tilt_neutral_when_off_or_spike() -> None:
    # weight=0 disables; spike tier (boost >= max_boost) keeps ceiling.
    assert _floor_tilt_multiplier(0.5, 2.0, 1.0, weight=0.0) == 1.0
    assert _floor_tilt_multiplier(0.5, 2.0, 2.5, weight=0.4, max_boost=2.0) == 1.0
    assert _floor_tilt_multiplier(0.5, 0.0, 1.0, weight=0.4) == 1.0


def test_floor_tilt_fades_wide_intervals_more() -> None:
    # Ogunbowale-vs-Shepard shape: same p50, but the volatile candidate's
    # p10 sits far below. The tilt fades her harder than the floor play.
    volatile = _floor_tilt_multiplier(0.4, 2.0, 1.0, weight=0.35)
    stable = _floor_tilt_multiplier(1.6, 2.0, 1.0, weight=0.35)
    assert volatile < stable < 1.0
    assert volatile == pytest.approx((0.65 * 2.0 + 0.35 * 0.4) / 2.0)


def test_floor_tilt_ignores_inverted_quantiles() -> None:
    # A p10 above p50 (degenerate head output) must not INFLATE the center.
    assert _floor_tilt_multiplier(3.0, 2.0, 1.0, weight=0.5) == 1.0


def test_head_path_wires_lift_and_tilt() -> None:
    # End-to-end through the job2 re-exports: the Harris 07-09 row (expected
    # starter, 18.04 recent minutes, boost 3.0) gets the lift and, being
    # spike-tier, no floor tilt.
    from wnba_oracle.scheduler import job2

    harris = json.dumps({"is_starter": 1, "rotowire_confirmed": 0, "recent_minutes": 18.04})
    lift = job2._starter_minutes_lift(harris, enabled=True)
    assert lift == pytest.approx((0.4 * 18.04 + 0.6 * 25.0) / 18.04)
    assert job2._floor_tilt_multiplier(0.5, 1.4, 3.0, weight=0.35) == 1.0
