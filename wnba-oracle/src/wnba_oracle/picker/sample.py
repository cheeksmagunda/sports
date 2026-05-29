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


@dataclass
class CopulaConfig:
    rho_same_team: float = -0.25
    rho_opp_team: float = +0.20
    seed: int = 1729


def build_correlation_matrix(
    specs: list[PlayerSamplingSpec], cfg: CopulaConfig
) -> np.ndarray:
    n = len(specs)
    R = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = specs[i], specs[j]
            if not a.team or not b.team:
                continue
            if a.team == b.team and a.opponent == b.opponent:
                R[i, j] = R[j, i] = cfg.rho_same_team
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
    # Convert log-scale samples back to real_score. The handoff says
    # real_score can be negative; we keep an offset so the exponential stays
    # numerically stable. Convention: store predictions in log(real_score + K)
    # space, K=10. Subtract K after exp.
    K = 10.0
    return np.exp(log_samples) - K


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
        lineup_samples[s] = float(
            np.sum(rs_sorted * (boosts_sorted + slot_multipliers))
        )
    return lineup_samples
