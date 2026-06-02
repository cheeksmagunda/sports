"""Joint sampling via Gaussian copula on log-residuals.

Per-player marginal distribution = N(mu_i, sigma_i^2) on log-scale, where
mu_i is the predicted log(real_score) and sigma_i is half the
calibrated band width from the predict pipeline.

Joint dependence is captured via a block-correlation matrix:
    Corr(player_a, player_b) = rho_same_team    if same team
                              rho_opp_team      if opposing teams in same game
                              0.0               if no game overlap

Defaults: rho_same_team = -0.25 (usage cannibalization);
          rho_opp_team =  +0.20 (shared pace realization).
These are conservative priors; calibration on the slate corpus tunes them.

Regime-switching (D57, Tier 3): the same-team correlation is not constant. In a
close game teammates cannibalize each other's usage (rho_same_team). In a likely
blowout the second unit shares one garbage-time regime, so two bench players
become positively correlated (either the blowout happens and they both play, or
it does not and they both sit), while a starter and a bench player substitute
(the starter sits as the bench plays), pushing their correlation more negative.
The same-team entry interpolates from rho_same_team toward the role-specific
blowout target by the pair's blowout_prob. With the spec defaults (is_starter
False, blowout_prob 0.0) the matrix is identical to the pre-D57 behaviour, so
nothing changes until a caller populates the blowout context.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PlayerSamplingSpec:
    player_id: int
    team: str
    opponent: str
    mu: float  # log-scale mean
    sigma: float  # log-scale std-dev
    boost: float
    is_starter: bool = False  # role tag for regime-switching correlation (D57)
    blowout_prob: float = 0.0  # this player's game blowout propensity in [0, 1]
    is_anchor: bool = False  # confirmed-minutes floor player for the anchor floor (D57)


@dataclass
class CopulaConfig:
    rho_same_team: float = -0.25
    rho_opp_team: float = +0.20
    seed: int = 1729
    # Regime-switching same-team correlation under a likely blowout (D57, Tier 3).
    # Interpolated from rho_same_team toward these targets by the pair's
    # blowout_prob. bench-bench positive (shared garbage-time regime),
    # starter-bench negative (substitution), starter-starter mildly negative.
    rho_bench_bench_blowout: float = +0.30
    rho_starter_bench_blowout: float = -0.35
    rho_starter_starter_blowout: float = -0.10
    # score_offset (K): log-sampling is done on log(real_score + K), then K is
    # subtracted after exp. K must exceed the most-negative real_score (corpus
    # min -0.39) to keep the log positive. D52 recalibrated K from 10 -> 2:
    # at K=10 the implied real_score std was ~3.2 (3x the observed ~1.17) and
    # the right-skew was flattened; at K=2 the implied std matches reality and
    # the lognormal skew is preserved. mu MUST be built with the same K (the
    # caller and this module share it via this field).
    score_offset: float = 2.0


def _same_team_rho(a: PlayerSamplingSpec, b: PlayerSamplingSpec, cfg: CopulaConfig) -> float:
    """Same-team correlation, regime-switched by blowout propensity (D57, Tier 3).

    Close game (blowout_prob 0) returns rho_same_team (cannibalization). As the
    pair's mean blowout_prob rises, interpolate toward a role-specific target:
    bench-bench positive (shared garbage-time regime), starter-bench negative
    (substitution), starter-starter mildly negative.
    """
    p = 0.5 * (a.blowout_prob + b.blowout_prob)
    if p <= 0.0:
        return cfg.rho_same_team
    p = min(1.0, p)
    if a.is_starter and b.is_starter:
        target = cfg.rho_starter_starter_blowout
    elif a.is_starter != b.is_starter:
        target = cfg.rho_starter_bench_blowout
    else:
        target = cfg.rho_bench_bench_blowout
    return (1.0 - p) * cfg.rho_same_team + p * target


def build_correlation_matrix(specs: list[PlayerSamplingSpec], cfg: CopulaConfig) -> np.ndarray:
    n = len(specs)
    R = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = specs[i], specs[j]
            if not a.team or not b.team:
                continue
            if a.team == b.team and a.opponent == b.opponent:
                R[i, j] = R[j, i] = _same_team_rho(a, b, cfg)
            elif a.team == b.opponent and b.team == a.opponent:
                R[i, j] = R[j, i] = cfg.rho_opp_team
    # Ensure PSD by light shrinkage if necessary
    return _make_psd(R)


def _make_psd(R: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    eigvals, eigvecs = np.linalg.eigh(R)
    eigvals = np.clip(eigvals, eps, None)
    return (eigvecs * eigvals) @ eigvecs.T


def sample_joint_real_scores(
    specs: list[PlayerSamplingSpec],
    n_samples: int,
    cfg: CopulaConfig = CopulaConfig(),
) -> np.ndarray:
    """Returns (n_samples, n_players) real_score samples for each player."""
    n = len(specs)
    if n == 0:
        return np.zeros((n_samples, 0))
    R = build_correlation_matrix(specs, cfg)
    L = np.linalg.cholesky(R)
    rng = np.random.default_rng(cfg.seed)
    z = rng.standard_normal((n_samples, n)) @ L.T
    mu = np.array([s.mu for s in specs])
    sigma = np.array([s.sigma for s in specs])
    log_samples = z * sigma + mu
    # Convert log-scale samples back to real_score. Predictions are stored in
    # log(real_score + K) space; subtract K after exp. K = cfg.score_offset
    # (D52). The caller MUST build mu with the same K.
    return np.exp(log_samples) - cfg.score_offset


def lineup_score_samples(
    real_score_samples: np.ndarray,
    boosts: np.ndarray,
    lineup_indices: list[int],
    slot_multipliers: np.ndarray,
) -> np.ndarray:
    """Compute lineup_score per sample for one candidate lineup.

    final_value_i = real_score_i * (boost_i + slot_mult_j)
    lineup_score   = sum over i in lineup

    `lineup_indices` is a list of 5 player indices into real_score_samples.
    `slot_multipliers` is the 5-vector of slot multipliers (descending).
    Slot assignment is by rearrangement inequality: highest real_score
    median → highest slot multiplier.
    """
    n_samples = real_score_samples.shape[0]
    lineup_samples = np.zeros(n_samples)
    rs_per_player = real_score_samples[:, lineup_indices]
    # Rank players within each sample so the highest real_score gets the
    # highest slot. This is the rearrangement-inequality assignment.
    boosts_lineup = boosts[lineup_indices]
    for s in range(n_samples):
        # kind='stable' for deterministic tie-breaking by input order
        order = np.argsort(rs_per_player[s], kind="stable")[::-1]  # high to low
        rs_sorted = rs_per_player[s, order]
        boosts_sorted = boosts_lineup[order]
        # slot_multipliers already sorted high to low
        lineup_samples[s] = float(np.sum(rs_sorted * (boosts_sorted + slot_multipliers)))
    return lineup_samples
