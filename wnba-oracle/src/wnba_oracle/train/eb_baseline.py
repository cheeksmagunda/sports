"""Empirical-Bayes hierarchical baseline.

Closed-form Gaussian-on-Gaussian shrinkage of per-player intercepts toward
the cohort mean. Own-model serving path (#523): EB is the default predictor;
LightGBM heads are optional. Robust on rookies and edge cases where trees
extrapolate badly.

Math:
    y_ij = mu_cohort + alpha_i + eps_ij,  eps ~ N(0, sigma2)
           alpha_i ~ N(0, tau2)
    posterior mean of alpha_i:
        alpha_hat_i = n_i * tau2 / (n_i * tau2 + sigma2) * (ybar_i - mu_cohort)

Used at predict time as:
    yhat_baseline = (
        mu_cohort_pred + alpha_hat_player
        + beta_team * (team_pace - league_pace)
        + beta_opp * (opp_pace - league_opp_pace)
        + beta_vegas * (vegas_total - league_vegas)
        + beta_boost * (card_boost - league_boost)
    )

Starter / confirmed-starter is applied at serve as a multiplier
(``_starter_multiplier``), not as a free-float EB coefficient.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import polars as pl


def _fit_linear_beta(
    residual: np.ndarray,
    x: np.ndarray,
) -> float:
    if x.size == 0 or float(x.var()) <= 1e-9:
        return 0.0
    return float(np.cov(x, residual, ddof=0)[0, 1] / x.var())


def _fit_centered_term(
    df: pl.DataFrame,
    y_resid: np.ndarray,
    col: str,
) -> tuple[float, float, np.ndarray]:
    """Return (beta, league_mean, residual_after) for one optional column."""

    if col not in df.columns:
        return 0.0, 0.0, y_resid
    mean_raw = df.get_column(col).mean()
    league = float(mean_raw) if isinstance(mean_raw, (int, float)) else 0.0
    x = (df.get_column(col).to_numpy() - league).astype(float)
    beta = _fit_linear_beta(y_resid, x)
    return beta, league, y_resid - beta * x


@dataclass
class EBHierarchicalBaseline:
    cohort_means: dict[str, float] = field(default_factory=dict)
    player_alpha: dict[int, float] = field(default_factory=dict)
    pace_beta: float = 0.0
    opp_pace_beta: float = 0.0
    vegas_beta: float = 0.0
    boost_beta: float = 0.0
    league_pace: float = 0.0
    league_opp_pace: float = 0.0
    league_vegas: float = 0.0
    league_boost: float = 0.0

    def fit(
        self,
        df: pl.DataFrame,
        *,
        target: str = "real_score",
        cohort_col: str = "cohort",
        player_col: str = "player_id",
        pace_col: str = "team_pace",
        opp_pace_col: str = "opp_pace",
        vegas_col: str = "vegas_total",
        boost_col: str = "card_boost",
    ) -> None:
        if df.is_empty():
            return
        # Per-cohort mean
        means = (df.group_by(cohort_col).agg(pl.col(target).mean().alias("mu"))).to_dicts()
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

        cohort_offset = np.array(
            [self.cohort_means.get(str(c), 0.0) for c in df.get_column(cohort_col).to_list()]
        )
        player_offset = np.array(
            [self.player_alpha.get(int(p), 0.0) for p in df.get_column(player_col).to_list()]
        )
        y_resid = df.get_column(target).to_numpy() - cohort_offset - player_offset

        self.pace_beta, self.league_pace, y_resid = _fit_centered_term(df, y_resid, pace_col)
        self.opp_pace_beta, self.league_opp_pace, y_resid = _fit_centered_term(
            df, y_resid, opp_pace_col
        )
        self.vegas_beta, self.league_vegas, y_resid = _fit_centered_term(df, y_resid, vegas_col)
        self.boost_beta, self.league_boost, _ = _fit_centered_term(df, y_resid, boost_col)

    def predict(self, df: pl.DataFrame) -> np.ndarray:
        if df.is_empty():
            return np.array([])
        cohorts = df.get_column("cohort").to_list() if "cohort" in df.columns else [None] * len(df)
        players = (
            df.get_column("player_id").to_list() if "player_id" in df.columns else [None] * len(df)
        )
        paces = (
            df.get_column("team_pace").to_numpy()
            if "team_pace" in df.columns
            else np.zeros(len(df))
        )
        opp_paces = (
            df.get_column("opp_pace").to_numpy() if "opp_pace" in df.columns else np.zeros(len(df))
        )
        vegas = (
            df.get_column("vegas_total").to_numpy()
            if "vegas_total" in df.columns
            else np.zeros(len(df))
        )
        boosts = (
            df.get_column("card_boost").to_numpy()
            if "card_boost" in df.columns
            else np.zeros(len(df))
        )
        out = np.zeros(len(df), dtype=float)
        for i, (c, p) in enumerate(zip(cohorts, players, strict=True)):
            mu = self.cohort_means.get(str(c), 0.0)
            alpha = self.player_alpha.get(int(p), 0.0) if p is not None else 0.0
            out[i] = (
                mu
                + alpha
                + self.pace_beta * (float(paces[i]) - self.league_pace)
                + self.opp_pace_beta * (float(opp_paces[i]) - self.league_opp_pace)
                + self.vegas_beta * (float(vegas[i]) - self.league_vegas)
                + self.boost_beta * (float(boosts[i]) - self.league_boost)
            )
        return out


def feature_subset(df: pl.DataFrame, cols: Iterable[str]) -> pl.DataFrame:
    cols = [c for c in cols if c in df.columns]
    return df.select(cols)


def attach_eb_residual_targets(
    df: pl.DataFrame,
    eb: EBHierarchicalBaseline,
    *,
    cohort_col: str = "cohort",
    real_score_col: str = "real_score",
) -> pl.DataFrame:
    """Set ``real_score_residual`` to realized ``real_score`` minus ``eb.predict``.

    ``add_targets`` leaves the column null until an EB model is fit; ``train_picker``
    calls this before training the ``real_score_residual`` head.
    """
    from wnba_oracle.features.spec import cohort_for_position

    if df.is_empty() or real_score_col not in df.columns:
        return df

    work = df
    if cohort_col not in work.columns:
        work = work.with_columns(
            pl.col("position")
            .map_elements(cohort_for_position, return_dtype=pl.String)
            .alias(cohort_col)
        )
    preds = eb.predict(work)
    observed = work.get_column(real_score_col).to_numpy().astype(float)
    return work.with_columns(pl.Series("real_score_residual", observed - preds, dtype=pl.Float64))
