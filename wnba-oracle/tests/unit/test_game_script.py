"""Game-script tier multipliers + blowout penalty."""

from __future__ import annotations

from wnba_oracle.picker.game_script import (
    GameScriptConfig,
    game_script_label,
    game_script_multiplier,
)


def test_label_thresholds_match_wnba_calibration() -> None:
    assert game_script_label(140.0) == "defensive_grind"
    assert game_script_label(160.0) == "balanced"
    assert game_script_label(170.0) == "fast_paced"
    assert game_script_label(180.0) == "track_meet"


def test_multipliers_are_monotone_increasing_through_track_meet() -> None:
    grind = game_script_multiplier(140.0, spread=2.0)
    balanced = game_script_multiplier(160.0, spread=2.0)
    fast = game_script_multiplier(170.0, spread=2.0)
    track = game_script_multiplier(180.0, spread=2.0)
    assert grind < balanced < fast < track


def test_blowout_penalty_only_fires_in_track_meet() -> None:
    """Blowout penalty downweights starters when the spread is wide AND
    the game is a track meet (high total)."""
    track_close = game_script_multiplier(180.0, spread=2.0)
    track_blowout = game_script_multiplier(180.0, spread=14.0)
    assert track_blowout < track_close
    # In a slower-paced blowout, the penalty does NOT kick in
    fast_blowout = game_script_multiplier(170.0, spread=14.0)
    fast_close = game_script_multiplier(170.0, spread=2.0)
    assert fast_blowout == fast_close


def test_custom_cfg_overrides_defaults() -> None:
    cfg = GameScriptConfig(balanced_mult=1.50, defensive_grind_mult=0.50)
    assert game_script_multiplier(160.0, spread=0.0, cfg=cfg) == 1.50
    assert game_script_multiplier(140.0, spread=0.0, cfg=cfg) == 0.50
