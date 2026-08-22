"""Knob-overlay shadow harness (2026-07-04, follow-up to model shadow D95).

The knob shadow replays the incumbent's head predictions through a hypothetical
picker knob overlay and logs a model_shadow_runs row so dayclose can backfill
the realized delta. These tests cover the pure ranking + hashing logic; the
persistence path is exercised end-to-end via the integration tests.
"""

from __future__ import annotations

from wnba_oracle.scheduler.shadow import (
    _apply_knob_overlay,
    _overlay_challenger_sha,
    _rank_with_overlay,
    _score_rank,
)


def test_overlay_sha_is_stable_across_key_order() -> None:
    a = _overlay_challenger_sha({"starter_unknown_fade": 0.75, "picker_boost_tail_lift": True})
    b = _overlay_challenger_sha({"picker_boost_tail_lift": True, "starter_unknown_fade": 0.75})
    assert a == b


def test_overlay_sha_carries_prefix() -> None:
    sha = _overlay_challenger_sha({})
    assert sha.startswith("knob_")


def test_starter_unknown_fade_reduces_rank_for_unknowns() -> None:
    # Unknown: is_starter=0 & rotowire_confirmed=0.
    features = {"is_starter": 0, "rotowire_confirmed": 0}
    baseline = _apply_knob_overlay(
        {"p10": 1.0, "p50": 2.0, "p90": 4.0}, boost=1.0, features=features, overlay={}
    )
    faded = _apply_knob_overlay(
        {"p10": 1.0, "p50": 2.0, "p90": 4.0},
        boost=1.0,
        features=features,
        overlay={"starter_unknown_fade": 0.75},
    )
    assert baseline == 2.0
    assert faded == 2.0 * 0.75


def test_starter_unknown_fade_does_not_touch_starters() -> None:
    starter = {"is_starter": 1, "rotowire_confirmed": 1}
    baseline = _apply_knob_overlay(
        {"p10": 1.0, "p50": 2.0, "p90": 4.0}, boost=0.5, features=starter, overlay={}
    )
    faded = _apply_knob_overlay(
        {"p10": 1.0, "p50": 2.0, "p90": 4.0},
        boost=0.5,
        features=starter,
        overlay={"starter_unknown_fade": 0.5},
    )
    # Confirmed starter always keeps 1.10, regardless of the fade.
    assert baseline == 2.0 * 1.10
    assert faded == 2.0 * 1.10


def test_boost_tail_lift_applies_only_above_threshold() -> None:
    features = {"is_starter": 0, "rotowire_confirmed": 0}
    overlay = {
        "picker_boost_tail_lift": True,
        "boost_tail_lift_threshold": 2.0,
        "boost_tail_lift_factor": 1.5,
    }
    below = _apply_knob_overlay(
        {"p10": 1.0, "p50": 2.0, "p90": 4.0}, boost=1.5, features=features, overlay=overlay
    )
    at = _apply_knob_overlay(
        {"p10": 1.0, "p50": 2.0, "p90": 4.0}, boost=2.0, features=features, overlay=overlay
    )
    above = _apply_knob_overlay(
        {"p10": 1.0, "p50": 2.0, "p90": 4.0}, boost=2.5, features=features, overlay=overlay
    )
    assert below == 2.0  # unchanged (baseline unknown mult 1.0)
    assert at == 2.0 * 1.5
    assert above == 2.0 * 1.5


def test_rank_with_overlay_matches_incumbent_when_empty() -> None:
    heads = {
        1: {"p10": 0.5, "p50": 3.0, "p90": 5.0},
        2: {"p10": 0.5, "p50": 2.0, "p90": 6.0},
    }
    boost = {1: 0.0, 2: 2.5}
    features = {1: {"is_starter": 1}, 2: {"is_starter": 0, "rotowire_confirmed": 0}}
    inc = _score_rank(heads, boost)
    ch = _rank_with_overlay(heads, boost, features, overlay={})
    assert inc == ch


def test_rank_with_overlay_promotes_boost_tail_when_lift_on() -> None:
    # Player 1: low-boost star, high p50. Player 2: high-boost role, low p50.
    heads = {
        1: {"p10": 0.5, "p50": 3.0, "p90": 5.0},
        2: {"p10": 0.5, "p50": 1.0, "p90": 6.0},
    }
    boost = {1: 0.0, 2: 2.5}
    features = {
        1: {"is_starter": 1, "rotowire_confirmed": 1},
        2: {"is_starter": 0, "rotowire_confirmed": 0},
    }
    # Baseline: star ranks first (3.0 * 2 = 6 vs 1.0 * 4.5 = 4.5).
    baseline = _rank_with_overlay(heads, boost, features, overlay={})
    assert baseline[0] == 1

    # Lift on with factor 1.5, plus unknown fade 0.75:
    #   star:  3.0 * 1.10 * 2   = 6.6
    #   role:  1.0 * 1.5 * 0.75 * 4.5 = 5.06
    # Star still wins.
    mild = _rank_with_overlay(
        heads,
        boost,
        features,
        overlay={
            "picker_boost_tail_lift": True,
            "boost_tail_lift_factor": 1.5,
            "starter_unknown_fade": 0.75,
        },
    )
    assert mild[0] == 1

    # Stronger lift with no unknown fade -> role flips to the top.
    strong = _rank_with_overlay(
        heads,
        boost,
        features,
        overlay={
            "picker_boost_tail_lift": True,
            "boost_tail_lift_factor": 2.0,
            "starter_unknown_fade": 1.0,
        },
    )
    assert strong[0] == 2
