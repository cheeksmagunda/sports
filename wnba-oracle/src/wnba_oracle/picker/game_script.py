"""Game-script tier multipliers and blowout adjustments.

Ported from basketball-main `_game_script_weights`, recalibrated for WNBA.
NBA totals run 215-250; WNBA totals run 145-180. The tier ceilings are
shifted accordingly.

Tiers:
- defensive_grind (< 155): low-scoring, defensive game. Slight downweight
  on points/rebounds, upweight on steals/blocks.
- balanced (155-165): neutral, no per-stat adjustment.
- fast_paced (165-175): up-tempo. Modest upweight on points/assists.
- track_meet (>= 175): high-pace shootout. Larger upweight on points,
  but if the spread is wide (>= 8) a blowout penalty kicks in - starters
  sit late in 30-point games.

This module returns a single scalar multiplier applied to the heuristic
real_score. Once the multi-task model ships, the per-stat weights become
useful and we will switch to applying them at the per-min-rate layer
(basketball-main's path).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameScriptConfig:
    defensive_grind_ceiling: float = 155.0
    balanced_ceiling: float = 165.0
    fast_paced_ceiling: float = 175.0
    blowout_spread_threshold: float = 8.0
    # Real-score multiplier per tier (1.0 = neutral)
    defensive_grind_mult: float = 0.95
    balanced_mult: float = 1.00
    fast_paced_mult: float = 1.04
    track_meet_mult: float = 1.07
    # Blowout penalty (multiplicative, applied on top of tier mult when
    # tier == track_meet AND abs(spread) > threshold)
    blowout_penalty: float = 0.92


def game_script_label(total: float, cfg: GameScriptConfig = GameScriptConfig()) -> str:
    """Human-readable label for the slate game-script."""
    if total < cfg.defensive_grind_ceiling:
        return "defensive_grind"
    if total <= cfg.balanced_ceiling:
        return "balanced"
    if total <= cfg.fast_paced_ceiling:
        return "fast_paced"
    return "track_meet"


def game_script_multiplier(
    total: float,
    spread: float,
    *,
    cfg: GameScriptConfig = GameScriptConfig(),
) -> float:
    """Return a single multiplier on real_score for a player whose game has
    the given total + absolute spread. Caller multiplies pred_real_score
    by this value before handing to the optimizer.
    """
    label = game_script_label(total, cfg)
    if label == "defensive_grind":
        m = cfg.defensive_grind_mult
    elif label == "balanced":
        m = cfg.balanced_mult
    elif label == "fast_paced":
        m = cfg.fast_paced_mult
    else:
        m = cfg.track_meet_mult
        if abs(spread or 0.0) >= cfg.blowout_spread_threshold:
            m *= cfg.blowout_penalty
    return float(m)
