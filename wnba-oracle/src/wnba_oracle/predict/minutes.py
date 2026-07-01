"""Minutes x per-minute-rate real_score predictor (D55).

Verified on the corpus (scripts/validate_minutes_model.py): real_score is
driven by minutes, the per-minute rate is stable, and minutes is the one
signal orthogonal to card_boost. corr(next real_score, ...) walk-forward on
2026, established players:
    actual_minutes x rate = +0.554   <- ceiling if tonight's minutes known
    recency minutes x rate = +0.355
    boost_prior           = +0.246
So even the recency baseline beats the boost, and the gap up to 0.554 is what
same-day role signals close.

Walk-forward PLACEMENT (scripts/test_minutes_placement.py), vs boost: the
history-weighted blend (boost prior shrinking toward minutes x rate as a
player accumulates games) tripled wins (1 -> 3 of 16), took best top-5 (4),
best gap-to-winner (11.44), best winner-overlap (1.56). That blend is what
ships, via `blended_real_score`.

E[real_score] = projected_minutes x per_minute_rate.

projected_minutes starts from recency-weighted recent minutes, then applies
the same-day role information the boost (a lagging average) cannot contain:
  - a RotoWire-confirmed start/sit overrides stale history (role change),
  - injury-cascade minutes inherited from OUT teammates (see
    features.injury_cascade.redistribute_minutes),
  - a blowout trim (starters sit in 30-point games).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class MinutesConfig:
    half_life: float = 3.0  # games; weight halves every half_life prior games
    league_rate: float = 0.095  # median per-minute real_score (cold-start rate)
    min_rate: float = 0.04
    max_rate: float = 0.18
    starter_minutes: float = 30.0  # projected minutes for a confirmed starter
    bench_minutes: float = 13.0  # projected minutes for a confirmed non-starter
    confirm_weight: float = 0.6  # how hard a confirmed role overrides stale history
    blowout_trim: float = 0.90  # starter minutes multiplier in a likely blowout
    min_minutes: float = 4.0
    max_minutes: float = 40.0
    min_obs_for_history: int = 2
    blend_k0: float = 3.0  # prior games of boost pull in the blend


def _ewma(vals: Sequence[float], half_life: float) -> tuple[float, float]:
    """(weighted_mean, weight_sum) over vals ordered MOST-RECENT-FIRST."""
    num = 0.0
    den = 0.0
    for i, v in enumerate(vals):
        w = 0.5 ** (i / half_life)
        num += w * float(v)
        den += w
    return (num / den, den) if den > 0 else (0.0, 0.0)


def recent_minutes(prior_min: Sequence[float], *, cfg: MinutesConfig = MinutesConfig()) -> float:
    """Recency-weighted recent minutes (the projection baseline)."""
    return _ewma(prior_min, cfg.half_life)[0]


def per_minute_rate(
    prior_real: Sequence[float],
    prior_min: Sequence[float],
    *,
    cfg: MinutesConfig = MinutesConfig(),
) -> float:
    """Stable per-minute real_score rate from prior (real, minutes), most-
    recent-first. Falls back to the league rate when history is thin."""
    if len(prior_real) < cfg.min_obs_for_history:
        return cfg.league_rate
    r_mean, _ = _ewma(prior_real, cfg.half_life)
    m_mean, _ = _ewma(prior_min, cfg.half_life)
    if m_mean <= 0:
        return cfg.league_rate
    return min(cfg.max_rate, max(cfg.min_rate, r_mean / m_mean))


def project_minutes_from_base(
    base_minutes: float,
    *,
    has_history: bool = True,
    rotowire_confirmed: bool = False,
    is_starter: bool = False,
    injury_bonus_min: float = 0.0,
    blowout: bool = False,
    cfg: MinutesConfig = MinutesConfig(),
) -> float:
    """Apply same-day role signals to a recency-minutes base.

    base_minutes is the recency-weighted recent minutes (or, when there is no
    history, ignored in favour of the confirmed-role anchor). A confirmed role
    pulls the projection toward the starter/bench anchor (captures promotions
    and demotions the rolling history lags); injury-cascade minutes add on top;
    a likely blowout trims a starter's minutes.
    """
    base = base_minutes
    if not has_history:
        base = cfg.starter_minutes if (rotowire_confirmed and is_starter) else cfg.bench_minutes
    if rotowire_confirmed:
        anchor = cfg.starter_minutes if is_starter else cfg.bench_minutes
        base = (1 - cfg.confirm_weight) * base + cfg.confirm_weight * anchor
    proj = base + max(0.0, injury_bonus_min)
    if blowout and base >= 24.0:  # only starters lose minutes to a blowout
        proj *= cfg.blowout_trim
    return min(cfg.max_minutes, max(cfg.min_minutes, proj))


def project_minutes(
    prior_min: Sequence[float],
    *,
    rotowire_confirmed: bool = False,
    is_starter: bool = False,
    injury_bonus_min: float = 0.0,
    blowout: bool = False,
    cfg: MinutesConfig = MinutesConfig(),
) -> float:
    """Project tonight's minutes from a prior-minutes series (offline path)."""
    have = len(prior_min) >= cfg.min_obs_for_history
    return project_minutes_from_base(
        recent_minutes(prior_min, cfg=cfg),
        has_history=have,
        rotowire_confirmed=rotowire_confirmed,
        is_starter=is_starter,
        injury_bonus_min=injury_bonus_min,
        blowout=blowout,
        cfg=cfg,
    )


def predict_real_score(
    prior_real: Sequence[float],
    prior_min: Sequence[float],
    *,
    rotowire_confirmed: bool = False,
    is_starter: bool = False,
    injury_bonus_min: float = 0.0,
    blowout: bool = False,
    cfg: MinutesConfig = MinutesConfig(),
) -> float:
    """E[real_score] = projected_minutes x per_minute_rate, floored at 0.5
    (offline series path)."""
    rate = per_minute_rate(prior_real, prior_min, cfg=cfg)
    proj = project_minutes(
        prior_min,
        rotowire_confirmed=rotowire_confirmed,
        is_starter=is_starter,
        injury_bonus_min=injury_bonus_min,
        blowout=blowout,
        cfg=cfg,
    )
    return max(0.5, proj * rate)


def blended_real_score(
    *,
    recent_min: float,
    rate: float,
    n_games: int,
    boost_prior: float,
    rotowire_confirmed: bool = False,
    is_starter: bool = False,
    injury_bonus_min: float = 0.0,
    blowout: bool = False,
    cfg: MinutesConfig = MinutesConfig(),
) -> float:
    """SHIPPED predictor (live path): blend the minutes prediction with the
    boost prior, weighting toward minutes as the player accumulates games.

    w = n_games / (n_games + blend_k0): a player with no minutes history is
    pure boost; a 10-game regular is ~0.77 minutes. The minutes side uses the
    precomputed recency base + same-day signals. boost_prior is the caller's
    cold-start E[real] for this player (e.g. job2._heuristic_real_score).
    """
    has_history = n_games >= cfg.min_obs_for_history
    if has_history:
        proj = project_minutes_from_base(
            recent_min,
            has_history=True,
            rotowire_confirmed=rotowire_confirmed,
            is_starter=is_starter,
            injury_bonus_min=injury_bonus_min,
            blowout=blowout,
            cfg=cfg,
        )
        minutes_pred = max(0.5, proj * rate)
    else:
        # No minutes history: still honour a confirmed start/sit if present.
        proj = project_minutes_from_base(
            recent_min,
            has_history=False,
            rotowire_confirmed=rotowire_confirmed,
            is_starter=is_starter,
            injury_bonus_min=injury_bonus_min,
            blowout=blowout,
            cfg=cfg,
        )
        minutes_pred = max(0.5, proj * (rate if rate > 0 else cfg.league_rate))
    w = n_games / (n_games + cfg.blend_k0)
    return max(0.5, w * minutes_pred + (1 - w) * float(boost_prior))


def minutes_volatility(
    prior_min: Sequence[float],
    *,
    default: float = 5.0,
    min_obs: int = 4,
) -> float:
    """Sample std of prior minutes -- drives sampling sigma. A locked-in
    starter (low minutes variance) is a floor play; a player whose minutes
    swing is a variance play. Returned in MINUTES units."""
    vals = list(prior_min)
    if len(vals) < min_obs:
        return default
    m = sum(vals) / len(vals)
    return (sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
