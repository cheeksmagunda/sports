"""Ownership projection (field model).

We do not have direct access to opponent lineups before lock. Approximate
ownership probability per player via a softmax of public-visible value:

    ownership_i = softmax( (pred_real_score_i * (1 + card_boost_i)) / tau )

Adjustments:
- Public injury question marks -> ownership down (multiplicative 0.6).
- Boost jumped vs prior slate -> ownership up (multiplicative 1.25).
- Nationally-televised / high-total game -> ownership up (multiplicative 1.15).

Use: for the lineup optimizer's top-20 / top-1 regimes, leverage =
sum over chosen players of (1 - ownership_i). Reward leverage in the
objective.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FieldPlayerSpec:
    player_id: int
    pred_real_score: float
    card_boost: float
    is_injury_question: bool = False
    boost_jump_vs_prior: bool = False
    national_tv: bool = False
    vegas_total_zscore: float = 0.0


def project_ownership(
    specs: list[FieldPlayerSpec],
    *,
    softmax_temperature: float = 6.0,
) -> np.ndarray:
    """Return a 1-D numpy array of ownership probabilities, summing to 1."""
    if not specs:
        return np.array([])
    raw = np.array(
        [s.pred_real_score * (1.0 + s.card_boost) for s in specs], dtype=float
    )
    raw = raw - raw.max()  # numerical stability
    base = np.exp(raw / max(softmax_temperature, 1e-6))
    # Multiplicative adjustments
    adj = np.ones_like(base)
    for i, s in enumerate(specs):
        if s.is_injury_question:
            adj[i] *= 0.6
        if s.boost_jump_vs_prior:
            adj[i] *= 1.25
        if s.national_tv or s.vegas_total_zscore > 1.0:
            adj[i] *= 1.15
    adjusted = base * adj
    total = adjusted.sum()
    if total <= 0.0:
        return np.full(len(specs), 1.0 / len(specs))
    return adjusted / total


def simulate_field_lineups(
    ownership: np.ndarray,
    *,
    n_lineups: int = 1000,
    lineup_size: int = 5,
    seed: int = 1729,
) -> np.ndarray:
    """Sample `n_lineups` opponent lineups under independent-pick-from-ownership.

    Returns an (n_lineups, lineup_size) integer index array. Same player
    can appear at most once per lineup. The independence assumption is a
    deliberate simplification; correlated public picks (stacks) are
    revisited in Step 8 once we have post-slate leaderboard scrapes.
    """
    rng = np.random.default_rng(seed)
    n = len(ownership)
    if n < lineup_size:
        raise ValueError(f"player pool too small ({n}) for lineup_size={lineup_size}")
    out = np.empty((n_lineups, lineup_size), dtype=int)
    for i in range(n_lineups):
        out[i] = rng.choice(n, size=lineup_size, replace=False, p=ownership)
    return out
