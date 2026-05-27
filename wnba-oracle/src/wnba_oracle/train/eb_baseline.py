"""Empirical-Bayes hierarchical baseline.

Closed-form Gaussian-on-Gaussian shrinkage of per-player intercepts toward
the cohort mean. Used as the 30%-weight ensemble member alongside LightGBM
(70%). Robust on rookies and edge cases where LightGBM extrapolates badly.

Math:
    y_ij = mu_cohort + alpha_i + eps_ij,  eps ~ N(0, sigma2)
           alpha_i ~ N(0, tau2)
    posterior mean of alpha_i:
        alpha_hat_i = n_i * tau2 / (n_i * tau2 + sigma2) * (ybar_i - mu_cohort)

Used at predict time as:
    yhat_baseline = mu_cohort_pred + alpha_hat_player + beta_team * (team_pace - league_pace)

team_pace effect is a single linear coefficient fit on training data.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import polars as pl


@dataclass
class EBHierarchicalBaseline:
    cohort_means: dict[str, float] = field(default_factory=dict)
    player_alpha: dict[int, float] = field(default_factory=dict)
    pace_beta: float = 0.0
    league_pace: float = 0.0

    def fit(
        self,
        df: pl.DataFrame,
        *,
        target: str = "real_score",
        cohort_col: str = "cohort",
        player_col: str = "player_id",
        pace_col: str = "team_pace",
    ) -> None:
        if df.is_empty():
            return
        # Per-cohort mean
        means = (
            df.group_by(cohort_col)
            .agg(pl.col(target).mean().alias("mu"))
        ).to_dicts()
        self.cohort_means = {str(r[cohort_col]): float(r["mu"]) for r in means}

        # Variance components
        ybar_per_player = df.group_by([player_col, cohort_col]).agg(
            [pl.col(target).mean().alias("ybar"), pl.col(target).count().alias("n")]
        )
        joined = df.join(ybar_per_player, on=[player_col, cohort_col], how="left")
        residual = joined.get_column(target).to_numpy() - joined.get_column("ybar").to_numpy()
        sigma2 = float(np.var(residual)) if residual.size > 0 else 1.0

        # Between-player variance
        per_player = ybar_per_player.to_dicts()
        intercepts = []
        for r in per_player:
            mu = self.cohort_means.get(str(r[cohort_col]), 0.0)
            intercepts.append(float(r["ybar"]) - mu)
        intercepts_arr = np.array(intercepts) if intercepts else np.array([0.0])
        tau2 = max(0.0, float(np.var(intercepts_arr)) - sigma2 / max(1, intercepts_arr.size))

        for r in per_player:
            mu = self.cohort_means.get(str(r[cohort_col]), 0.0)
            n_i = int(r["n"]) if r["n"] is not None else 0
            ybar_i = float(r["ybar"])
            shrink = n_i * tau2 / (n_i * tau2 + sigma2) if (n_i * tau2 + sigma2) > 0 else 0.0
            self.player_alpha[int(r[player_col])] = shrink * (ybar_i - mu)

        # Single linear pace effect (least-squares on residuals).
        if pace_col in df.columns:
            mean_pace = df.get_column(pace_col).mean()
            if isinstance(mean_pace, (int, float)):
                league_pace = float(mean_pace)
            else:
                league_pace = 0.0
        else:
            league_pace = 0.0
        self.league_pace = league_pace
        if pace_col in df.columns:
            x = (df.get_column(pace_col).to_numpy() - league_pace).astype(float)
            y = (
                df.get_column(target).to_numpy()
                - np.array([self.cohort_means.get(str(c), 0.0) for c in df.get_column(cohort_col).to_list()])
                - np.array([self.player_alpha.get(int(p), 0.0) for p in df.get_column(player_col).to_list()])
            )
            if x.var() > 1e-9:
                self.pace_beta = float(np.cov(x, y, ddof=0)[0, 1] / x.var())
            else:
                self.pace_beta = 0.0

    def predict(self, df: pl.DataFrame) -> np.ndarray:
        if df.is_empty():
            return np.array([])
        cohorts = df.get_column("cohort").to_list() if "cohort" in df.columns else [None] * len(df)
        players = df.get_column("player_id").to_list() if "player_id" in df.columns else [None] * len(df)
        paces = (
            df.get_column("team_pace").to_numpy()
            if "team_pace" in df.columns
            else np.zeros(len(df))
        )
        out = np.zeros(len(df), dtype=float)
        for i, (c, p) in enumerate(zip(cohorts, players, strict=True)):
            mu = self.cohort_means.get(str(c), 0.0)
            alpha = self.player_alpha.get(int(p), 0.0) if p is not None else 0.0
            out[i] = mu + alpha + self.pace_beta * (float(paces[i]) - self.league_pace)
        return out


def feature_subset(df: pl.DataFrame, cols: Iterable[str]) -> pl.DataFrame:
    cols = [c for c in cols if c in df.columns]
    return df.select(cols)
