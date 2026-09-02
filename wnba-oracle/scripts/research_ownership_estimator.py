"""Research script: learned pre-lock WNBA ownership estimator.

Trains a machine learning model on finalized drafts using causal features
available before lock, and evaluates if it can improve upon the baseline estimator
fallback.
"""

from __future__ import annotations

import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import PoissonRegressor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wnba_oracle.picker.popularity import WNBA_BIG_MARKETS, estimate_draft_popularity


def load_and_prepare_data() -> pd.DataFrame:
    # Load slate labels
    csv_path = Path(__file__).resolve().parents[1] / "data" / "backups" / "slate_labels.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Backup file not found at {csv_path}. Run git checkout origin/backups first."
        )

    df = pd.read_csv(csv_path)
    df = df.sort_values("slate_date").copy()

    # Filter to valid drafts
    df = df.dropna(subset=["drafts"]).copy()

    # Compute slate size (number of teams on the slate)
    slate_sizes = df.groupby("slate_date")["team_key"].nunique().to_dict()
    df["slate_size"] = df["slate_date"].map(slate_sizes)
    df["n_games_on_slate"] = (df["slate_size"] // 2).clip(lower=1)

    # Compute is_big_market
    df["is_big_market"] = df["team_key"].apply(
        lambda t: 1 if str(t).upper() in WNBA_BIG_MARKETS else 0
    )

    # Compute causal recent real_score (expanding mean of prior games)
    df["recent_real_score"] = df.groupby("platform_player_id")["real_score"].transform(
        lambda x: x.shift(1).expanding(min_periods=1).mean()
    )
    # Cold-start fallback
    df["recent_real_score"] = df["recent_real_score"].fillna(2.0)

    # Compute baseline projected ownership estimate
    df["baseline_pop"] = df.apply(
        lambda r: estimate_draft_popularity(
            season_ppg=10.0 + (3.0 - float(r["card_boost"])) * 4.0,
            team=str(r["team_key"]),
            n_games_on_slate=int(r["n_games_on_slate"]),
        ),
        axis=1,
    )

    return df


def evaluate_slate_metrics(
    df_eval: pd.DataFrame, pred_col: str, baseline_col: str = "baseline_pop"
) -> dict[str, float]:
    corrs_pred = []
    corrs_base = []
    overlap_pred = []
    overlap_base = []

    for _sd, g in df_eval.groupby("slate_date"):
        if len(g) < 2:
            continue
        actual = g["drafts"].to_numpy()
        p_val = g[pred_col].to_numpy()
        b_val = g[baseline_col].to_numpy()

        # Rank correlations
        cp = spearmanr(actual, p_val).correlation
        cb = spearmanr(actual, b_val).correlation
        if not np.isnan(cp):
            corrs_pred.append(cp)
        if not np.isnan(cb):
            corrs_base.append(cb)

        # Top-20 overlap
        k = min(20, len(g))
        if k > 0:
            top_actual = set(g.nlargest(k, "drafts")["platform_player_id"])
            top_pred = set(g.nlargest(k, pred_col)["platform_player_id"])
            top_base = set(g.nlargest(k, baseline_col)["platform_player_id"])

            overlap_pred.append(len(top_actual & top_pred) / k)
            overlap_base.append(len(top_actual & top_base) / k)

    return {
        "mean_rank_corr_base": float(np.mean(corrs_base)) if corrs_base else 0.0,
        "mean_rank_corr_pred": float(np.mean(corrs_pred)) if corrs_pred else 0.0,
        "mean_top20_overlap_base": float(np.mean(overlap_base)) if overlap_base else 0.0,
        "mean_top20_overlap_pred": float(np.mean(overlap_pred)) if overlap_pred else 0.0,
    }


def main() -> int:
    df = load_and_prepare_data()

    # Time-based split: Train on 2025, Test on 2026
    train = df[df["slate_date"] < "2026-01-01"].copy()
    test = df[df["slate_date"] >= "2026-01-01"].copy()

    print("=" * 80)
    print("WNBA LEARNED PRE-LOCK OWNERSHIP ESTIMATOR RESEARCH")
    print("=" * 80)
    print(f"Total rows: {len(df)}")
    print(f"Train (2025) rows: {len(train)} across {train['slate_date'].nunique()} slates")
    print(f"Test (2026) rows: {len(test)} across {test['slate_date'].nunique()} slates\n")

    # Features and target
    X_cols = ["card_boost", "slate_size", "is_big_market", "recent_real_score", "baseline_pop"]
    y_col = "drafts"

    X_train, y_train = train[X_cols], train[y_col]
    X_test = test[X_cols]

    # Model 1: LightGBM Regressor (Default MSE)
    lgb_model = lgb.LGBMRegressor(random_state=42, verbose=-1)
    lgb_model.fit(X_train, y_train)
    test = test.copy()
    test["pred_lgb"] = lgb_model.predict(X_test)

    # Model 2: LightGBM Poisson Regressor
    lgb_poisson = lgb.LGBMRegressor(objective="poisson", random_state=42, verbose=-1)
    lgb_poisson.fit(X_train, y_train)
    test["pred_lgb_poisson"] = lgb_poisson.predict(X_test)

    # Model 3: Sklearn Poisson Regressor
    poisson_model = PoissonRegressor()
    poisson_model.fit(X_train, y_train)
    test["pred_poisson_sk"] = poisson_model.predict(X_test)

    # Evaluation
    metrics_lgb = evaluate_slate_metrics(test, "pred_lgb")
    metrics_lgb_p = evaluate_slate_metrics(test, "pred_lgb_poisson")
    metrics_poisson = evaluate_slate_metrics(test, "pred_poisson_sk")

    print("--- Model Performance Comparison (on 2026 Test Slates) ---")
    print("Baseline Heuristic Estimator:")
    print(f"  Mean Spearman Rank Corr  = {metrics_lgb['mean_rank_corr_base']:.4f}")
    print(f"  Mean Top-20 Overlap      = {metrics_lgb['mean_top20_overlap_base']:.2%}")

    print("\nLightGBM Regressor (MSE):")
    print(f"  Mean Spearman Rank Corr  = {metrics_lgb['mean_rank_corr_pred']:.4f}")
    print(f"  Mean Top-20 Overlap      = {metrics_lgb['mean_top20_overlap_pred']:.2%}")
    print(
        f"  Improvement in Rank Corr = {metrics_lgb['mean_rank_corr_pred'] - metrics_lgb['mean_rank_corr_base']:+.4f}"
    )
    print(
        f"  Improvement in Overlap   = {metrics_lgb['mean_top20_overlap_pred'] - metrics_lgb['mean_top20_overlap_base']:+.2%}"
    )

    print("\nLightGBM Poisson Regressor:")
    print(f"  Mean Spearman Rank Corr  = {metrics_lgb_p['mean_rank_corr_pred']:.4f}")
    print(f"  Mean Top-20 Overlap      = {metrics_lgb_p['mean_top20_overlap_pred']:.2%}")
    print(
        f"  Improvement in Rank Corr = {metrics_lgb_p['mean_rank_corr_pred'] - metrics_lgb_p['mean_rank_corr_base']:+.4f}"
    )
    print(
        f"  Improvement in Overlap   = {metrics_lgb_p['mean_top20_overlap_pred'] - metrics_lgb_p['mean_top20_overlap_base']:+.2%}"
    )

    print("\nSklearn Poisson Regressor:")
    print(f"  Mean Spearman Rank Corr  = {metrics_poisson['mean_rank_corr_pred']:.4f}")
    print(f"  Mean Top-20 Overlap      = {metrics_poisson['mean_top20_overlap_pred']:.2%}")
    print(
        f"  Improvement in Rank Corr = {metrics_poisson['mean_rank_corr_pred'] - metrics_poisson['mean_rank_corr_base']:+.4f}"
    )
    print(
        f"  Improvement in Overlap   = {metrics_poisson['mean_top20_overlap_pred'] - metrics_poisson['mean_top20_overlap_base']:+.2%}"
    )

    print("\n" + "=" * 80)
    print("CONCLUSION AND STRATEGY RECOMENDATION:")
    print("=" * 80)
    lgb_p_corr_improve = metrics_lgb_p["mean_rank_corr_pred"] - metrics_lgb_p["mean_rank_corr_base"]
    if lgb_p_corr_improve > 0.01:
        print(
            "SUCCESS: The learned estimator (LightGBM Poisson) beats the baseline fallback estimator!"
        )
        print(
            f"Rank Correlation improved by {lgb_p_corr_improve:+.4f} and Top-20 Overlap by {metrics_lgb_p['mean_top20_overlap_pred'] - metrics_lgb_p['mean_top20_overlap_base']:+.2%}."
        )
        print(
            "We recommend training and deploying the learned Poisson model to replace the heuristic fallback."
        )
    else:
        print(
            "NEGATIVE RESULT: The learned models do NOT significantly beat the baseline heuristic fallback."
        )
        print(
            "The current estimator fallback is extremely robust and captures the primary signals (market size, slate size, boost value) effectively."
        )
        print(
            "Therefore, we recommend keeping the baseline heuristic as the fallback pre-lock ownership estimator,"
        )
        print(
            "as adding a machine learning model does not provide a meaningful predictive lift on these features."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
