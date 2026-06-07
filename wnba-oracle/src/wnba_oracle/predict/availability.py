"""Two-part availability model (D57, Tier 2).

E[real_score] = P(active) x E[real_score | active]. The minutes model (D55) gives
the active-conditional value (projected_minutes x per-minute rate); this module
estimates P(active): the probability the player is in tonight's rotation and
logs a meaningful shift.

The 2026-06-01 bust was caused by treating cold-start darts (no minutes history)
as if they would play. The heuristic handed a boost-3 rookie ~1.81 active-value
and the additive boost made the optimizer love them; they logged ~0 minutes.
P(active) for a player with no rotation evidence is LOW, which multiplies that
fake value down to nothing -- and it is the signal that separates the boost
longshot that wins a slate (Kosu, a real rotation player) from the one that
busts it (Holmes, a deep-bench dart).

Small-data regime: this is an empirical-Bayes shrinkage, not a trained
classifier (which would overfit the ~500-row corpus). The within-game floor
probability P(min >= active_floor | recent minutes, vol) is shrunk toward a
neutral rate by how many games of history exist; a player with NO history falls
to a low base rate; confirmed starters/bench (RotoWire) are pulled up.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class AvailabilityConfig:
    active_minutes_floor: float = 10.0  # a "meaningful shift" worth a roster spot
    min_vol: float = 4.0  # floor on the minutes std used in the normal CDF
    # D73 (R9 refinement): empirical recalibration over the 13,002-row
    # gamelog corpus (scripts/research/availability_calibration.py).
    # Per-bin P(min >= 10):
    #   mins_l5 [0,  5): 0.204  (n=432, cold/bench)
    #   mins_l5 [5, 15): 0.554  (n=3397, rotation bench)
    #   mins_l5 [15,25): 0.906  (n=4252, starter)
    #   mins_l5 [25,+): 0.991  (n=4921, elite starter)
    # The previous neutral_prior=0.60 over-trusted "any-history" players;
    # 0.55 matches the rotation-bench bucket empirically. prior_active was
    # 0.30 for no-history; cold-start darts (the 2026-06-04 ~6000th bust
    # class) deserve the [0,5) rate of 0.20.
    neutral_prior: float = 0.55  # shrinkage target for players WITH some history
    prior_active: float = 0.20  # base rate for a no-history player (a probable dart)
    confirmed_starter_active: float = 0.92
    confirmed_bench_active: float = 0.70
    confidence_k0: float = 4.0  # games of history needed to half-trust the data
    p_min: float = 0.05
    p_max: float = 1.0


def _norm_sf(z: float) -> float:
    """P(Z > z) for a standard normal, via erfc (no scipy dependency)."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def availability_probability(
    *,
    recent_minutes: float,
    minutes_vol: float,
    n_min_games: int,
    rotowire_confirmed: bool = False,
    is_starter: bool = False,
    cfg: AvailabilityConfig = AvailabilityConfig(),
) -> float:
    """P(player is active and logs >= active_minutes_floor minutes tonight).

    With history, this is the within-game floor probability shrunk toward a
    neutral rate by sample size. With no history, it is the low base rate.
    Confirmed roles set a floor on the result.
    """
    if n_min_games > 0 and recent_minutes > 0.0:
        vol = max(minutes_vol, cfg.min_vol)
        floor_prob = _norm_sf((cfg.active_minutes_floor - recent_minutes) / vol)
        conf = n_min_games / (n_min_games + cfg.confidence_k0)
        p = conf * floor_prob + (1.0 - conf) * cfg.neutral_prior
    else:
        # No nba_api rotation evidence: treat as a probable dart unless a
        # same-day role signal says otherwise (handled just below).
        p = cfg.prior_active

    if rotowire_confirmed and is_starter:
        p = max(p, cfg.confirmed_starter_active)
    elif rotowire_confirmed:
        p = max(p, cfg.confirmed_bench_active)

    return min(cfg.p_max, max(cfg.p_min, p))
