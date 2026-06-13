"""Ownership projection (field model).

We do not have direct access to opponent lineups before lock. Two paths:

1. MEASURED (preferred, D86). Real Sports shows each player's live draft
   count in-app pre-lock; job1 captures it into `slate_labels.drafts`. When a
   spec carries `measured_drafts`, the field ownership marginal IS that count
   (normalized). This is the single most predictive ownership signal and it is
   observed, not modelled. Players missing a count (late pool entrants not yet
   in slate_labels) are back-filled from the estimator below, rescaled onto the
   measured magnitude so the two scales are comparable.

2. ESTIMATOR (fallback, pre-D86 behaviour). Approximate ownership probability
   per player via a softmax of public-visible value:

       ownership_i = softmax( (pred_real_score_i * (1 + card_boost_i)) / tau )

   Adjustments:
   - Public injury question marks -> ownership down (multiplicative 0.6).
   - Boost jumped vs prior slate -> ownership up (multiplicative 1.25).
   - Nationally-televised / high-total game -> ownership up (multiplicative 1.15).

Why this matters (D86): the estimator re-derives the field from OUR OWN
projections, so the simulated field drafts exactly what our value model says is
good. Against that strawman the optimizer cannot see real duplication and
systematically underprices leverage -- it ships chalk that the live field also
owns heavily, then finishes mid-pack when those chalk cards merely meet
projection. Feeding the real, concentrated draft counts makes the EV/rank math
penalize duplicated chalk and reward differentiated ceiling the way a
top-heavy contest actually pays.

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
    # D86: measured draft count for this player from slate_labels.drafts
    # (the in-app ownership shown pre-lock). None means "not observed"; the
    # estimator back-fills it. When any spec carries a measured count the
    # field marginal is built from the real counts, not the estimator.
    measured_drafts: float | None = None


def _estimated_ownership_unnormalized(
    specs: list[FieldPlayerSpec], softmax_temperature: float
) -> np.ndarray:
    """Pre-D86 estimator: softmax of public-visible value with multiplicative
    adjustments. Returns an UNNORMALIZED weight per spec."""
    raw = np.array(
        [s.pred_real_score * (1.0 + s.card_boost) for s in specs], dtype=float
    )
    raw = raw - raw.max()  # numerical stability
    base = np.exp(raw / max(softmax_temperature, 1e-6))
    adj = np.ones_like(base)
    for i, s in enumerate(specs):
        if s.is_injury_question:
            adj[i] *= 0.6
        if s.boost_jump_vs_prior:
            adj[i] *= 1.25
        if s.national_tv or s.vegas_total_zscore > 1.0:
            adj[i] *= 1.15
    return base * adj


def project_ownership(
    specs: list[FieldPlayerSpec],
    *,
    softmax_temperature: float = 6.0,
) -> np.ndarray:
    """Return a 1-D numpy array of ownership probabilities, summing to 1.

    Measured path (D86): if any spec carries `measured_drafts`, the ownership
    marginal is the real draft counts. Players missing a count are back-filled
    from the estimator, rescaled to the median measured magnitude so the two
    sources sit on a comparable scale before normalization. When no spec has a
    measured count this is byte-identical to the pre-D86 estimator.
    """
    if not specs:
        return np.array([])

    estimated = _estimated_ownership_unnormalized(specs, softmax_temperature)

    measured = np.array(
        [s.measured_drafts if s.measured_drafts is not None else np.nan for s in specs],
        dtype=float,
    )
    have = np.isfinite(measured)
    if have.any():
        filled = np.where(have, measured, 0.0)
        if (~have).any():
            # Rescale the estimator onto the measured scale via the median of
            # the players we DID observe, so an unobserved late entrant is
            # inserted at a plausible magnitude rather than dwarfing or
            # vanishing against raw draft counts.
            measured_med = float(np.median(measured[have]))
            est_have_med = float(np.median(estimated[have])) if have.any() else 0.0
            # Fall back to the global estimator median if every observed
            # player happened to have a zero estimator weight.
            if est_have_med <= 0.0:
                est_have_med = float(np.median(estimated)) or 1.0
            scale = measured_med / est_have_med if est_have_med > 0.0 else 0.0
            filled = np.where(have, filled, estimated * scale)
        filled = np.clip(filled, 0.0, None)
        total = filled.sum()
        if total > 0.0:
            return filled / total

    total = estimated.sum()
    if total <= 0.0:
        return np.full(len(specs), 1.0 / len(specs))
    return estimated / total


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
    deliberate simplification; the stack-aware sampler below (D88) lifts it
    when game/team keys are wired through the optimizer.
    """
    rng = np.random.default_rng(seed)
    n = len(ownership)
    if n < lineup_size:
        raise ValueError(f"player pool too small ({n}) for lineup_size={lineup_size}")
    out = np.empty((n_lineups, lineup_size), dtype=int)
    for i in range(n_lineups):
        out[i] = rng.choice(n, size=lineup_size, replace=False, p=ownership)
    return out


def simulate_field_lineups_correlated(
    ownership: np.ndarray,
    *,
    game_keys: list[str],
    team_keys: list[str],
    same_game_boost: float = 1.0,
    same_team_boost: float = 1.0,
    n_lineups: int = 1000,
    lineup_size: int = 5,
    seed: int = 1729,
) -> np.ndarray:
    """Sample correlated opponent lineups (D88 / Phase 3).

    The independent-pick sampler treats every roster slot as an iid draw from
    the marginal ownership. Real GPP fields stack: the project's
    `research/internal/01_winners_anatomy.md` records 87% of top-20 lineups
    carrying at least one 2+ same-game group. Modeling that correlation tightens
    the rank distribution at the top (where chalk concentrates) and is the
    second half of the keystone D86 fix -- without it our EV/rank math still
    assumes the field is uncorrelated even when its marginals are right.

    Sampling algorithm: sequential weighted draw-without-replacement. After
    each pick, the remaining-weight vector is multiplied by `same_team_boost`
    on the picked player's teammates and by `same_game_boost` on the
    opposite-team players in the same game (boosts compound across picks).
    Default boosts are 1.0 so without callers this is identical in expectation
    to the independent sampler. game_keys are typically the unordered
    `{team, opponent}` pair; team_keys is the player's own team.

    Returns an (n_lineups, lineup_size) integer index array.
    """
    if same_game_boost == 1.0 and same_team_boost == 1.0:
        return simulate_field_lineups(
            ownership, n_lineups=n_lineups, lineup_size=lineup_size, seed=seed
        )
    rng = np.random.default_rng(seed)
    n = len(ownership)
    if n < lineup_size:
        raise ValueError(f"player pool too small ({n}) for lineup_size={lineup_size}")
    if len(game_keys) != n or len(team_keys) != n:
        raise ValueError("game_keys / team_keys must match ownership length")
    # Build same-game / same-team boolean masks once; the per-pick work is then
    # an O(n) gather + multiply rather than an O(n) string comparison.
    game_idx: dict[str, np.ndarray] = {}
    team_idx: dict[str, np.ndarray] = {}
    for k in set(game_keys):
        if k:
            game_idx[k] = np.array([g == k for g in game_keys])
    for k in set(team_keys):
        if k:
            team_idx[k] = np.array([t == k for t in team_keys])
    out = np.empty((n_lineups, lineup_size), dtype=int)
    base = np.asarray(ownership, dtype=float)
    for i in range(n_lineups):
        w = base.copy()
        for slot in range(lineup_size):
            tot = w.sum()
            if tot <= 0.0:
                # All remaining weight evaporated. Fall back to uniform on the
                # players not yet picked so we never crash a sample mid-lineup.
                picked = set(out[i, :slot])
                w = np.array([0.0 if j in picked else 1.0 for j in range(n)])
                tot = w.sum()
            p = w / tot
            chosen = int(rng.choice(n, p=p))
            out[i, slot] = chosen
            w[chosen] = 0.0
            tk = team_keys[chosen]
            gk = game_keys[chosen]
            if tk and same_team_boost != 1.0:
                w = np.where(team_idx[tk], w * same_team_boost, w)
            if gk and same_game_boost != 1.0:
                w = np.where(game_idx[gk], w * same_game_boost, w)
    return out
