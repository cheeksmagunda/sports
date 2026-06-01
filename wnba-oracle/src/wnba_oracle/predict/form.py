"""Boost prior, per-player volatility, and a recency challenger (NOT shipped).

D52 finding (verified walk-forward, `scripts/backtest_walkforward.py`):
recency-weighting a player's prior real_scores does NOT beat the card_boost
prior. corr(next_real_score, recency_EWMA) = +0.448 and
corr(next_real_score, boost_prior) = +0.448 -- identical, MAE tied at ~1.08.
The reason: card_boost is the platform's rolling-rating handicap, so it
ALREADY encodes recent player form. Adding our own recency on top is
redundant and injects idiosyncratic noise, so the form predictor scores
slightly WORSE than boost-only on out-of-sample ceil_contrib ranking. The
only pre-game signal additive to boost is same-day minutes/role (confirmed
starter), which boost (a lagging average) cannot contain -- handled in
job2 via the RotoWire starter flag, not here.

What this module ships into the serving path:
- `boost_prior`: the calibrated boost handicap (D43), the base predictor.
- `player_volatility`: per-player real_score std, for per-player sampling
  sigma (ceiling plays priced as ceiling).

`predict_real_scores` (the recency blend) is RETAINED only as the documented
challenger the walk-forward harness compares against; it is deliberately NOT
wired into job2. Do not promote it without a walk-forward win.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


def boost_prior(card_boost: float) -> float:
    """Cold-start prior: the calibrated boost handicap relation (D43).

    Kept in sync with job2._heuristic_real_score on purpose -- both express
    "expected real_score for a player at this boost level with no other
    signal." Floored at 0.5 so it is a usable log-sampling centre.
    """
    return max(0.5, 3.16 - 0.45 * float(card_boost))


@dataclass(frozen=True)
class FormConfig:
    half_life: float = 4.0  # slates; weight halves every `half_life` prior games
    prior_strength: float = 2.0  # k0: equivalent prior games of boost_prior pull
    max_lookback: int = 12  # ignore games older than this many prior slates


def _ewma(prior_scores: Sequence[float], cfg: FormConfig) -> tuple[float, float]:
    """Return (weighted_mean, n_eff) over prior real_scores, most-recent first.

    `prior_scores` must be ordered most-recent-first. Empty -> (0.0, 0.0).
    """
    num = 0.0
    den = 0.0
    for i, s in enumerate(prior_scores[: cfg.max_lookback]):
        w = 0.5 ** (i / cfg.half_life)
        num += w * float(s)
        den += w
    if den <= 0.0:
        return 0.0, 0.0
    return num / den, den


def predict_real_scores(
    prior_by_player: Mapping[int, Sequence[float]],
    boost_by_player: Mapping[int, float],
    *,
    cfg: FormConfig = FormConfig(),
) -> dict[int, float]:
    """Form-aware prediction for every player in `boost_by_player`.

    prior_by_player: {player_id: [real_score, ...]} ordered MOST-RECENT-FIRST,
      containing only slates strictly before the target slate. Players absent
      here (or with an empty list) fall back to the pure boost prior.
    boost_by_player: {player_id: card_boost} for the slate pool.

    Returns {player_id: predicted_real_score}, floored at 0.5.
    """
    out: dict[int, float] = {}
    for pid, boost in boost_by_player.items():
        prior = prior_by_player.get(int(pid), ())
        recent, n_eff = _ewma(prior, cfg)
        prior_mean = boost_prior(boost)
        blended = (n_eff * recent + cfg.prior_strength * prior_mean) / (
            n_eff + cfg.prior_strength
        )
        out[int(pid)] = max(0.5, float(blended))
    return out


def player_volatility(
    prior_by_player: Mapping[int, Sequence[float]],
    *,
    default: float = 1.17,
    min_sigma: float = 0.7,
    max_sigma: float = 1.8,
    min_obs: int = 4,
) -> dict[int, float]:
    """Per-player real_score volatility (sample std of prior scores), clamped.

    Drives per-player sampling spread so high-variance ceiling plays are priced
    as ceiling and high-floor starters as floor, instead of the flat sigma the
    sampler used before. Players with < min_obs prior games get `default` (the
    league per-player median std). Returned in REAL_SCORE units; the sampler
    converts to its log-scale sigma.
    """
    out: dict[int, float] = {}
    for pid, scores in prior_by_player.items():
        vals = list(scores)
        if len(vals) < min_obs:
            out[int(pid)] = default
            continue
        m = sum(vals) / len(vals)
        var = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
        sd = var**0.5
        out[int(pid)] = min(max_sigma, max(min_sigma, sd))
    return out
