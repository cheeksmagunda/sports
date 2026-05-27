"""Adversarial validation gate.

Train a binary classifier to distinguish train rows from serve / holdout
rows. If AUC > 0.6, train and serve distributions differ enough to break
calibration; the promotion is blocked (Hard Rule from Part 6.5).

Common causes: feature freshness mismatch, schema drift, roster turnover.
"""

from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import polars as pl
from sklearn.metrics import roc_auc_score


@dataclass
class AdversarialResult:
    auc: float
    top_features: list[tuple[str, float]]
    n_train: int
    n_serve: int


def run_adversarial_validation(
    train_df: pl.DataFrame,
    serve_df: pl.DataFrame,
    *,
    feature_columns: list[str] | None = None,
    seed: int = 1729,
    n_trees: int = 200,
) -> AdversarialResult:
    """Fit a LightGBM binary classifier on (train=0, serve=1). Return AUC +
    top SHAP-like feature importances. AUC > 0.6 should block promotion."""
    if train_df.is_empty() or serve_df.is_empty():
        return AdversarialResult(auc=0.0, top_features=[], n_train=len(train_df), n_serve=len(serve_df))

    cols = feature_columns or [
        c for c in train_df.columns if c in serve_df.columns and train_df[c].dtype.is_numeric()
    ]
    if not cols:
        return AdversarialResult(auc=0.0, top_features=[], n_train=len(train_df), n_serve=len(serve_df))

    X_train = train_df.select(cols).fill_null(0.0).to_pandas()
    X_serve = serve_df.select(cols).fill_null(0.0).to_pandas()
    X = np.vstack([X_train.to_numpy(), X_serve.to_numpy()])
    y = np.concatenate([np.zeros(len(X_train)), np.ones(len(X_serve))])

    # Simple holdout split: 70/30.
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(X))
    cut = int(len(X) * 0.7)
    tr, te = idx[:cut], idx[cut:]
    params = {
        "objective": "binary",
        "metric": "auc",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbosity": -1,
        "seed": seed,
        "deterministic": True,
        "force_col_wise": True,
    }
    train_set = lgb.Dataset(X[tr], label=y[tr], feature_name=cols)
    booster = lgb.train(params, train_set, num_boost_round=n_trees)
    preds = booster.predict(X[te])
    try:
        auc = float(roc_auc_score(y[te], preds))
    except ValueError:
        auc = 0.0
    importance = booster.feature_importance(importance_type="gain")
    pairs = sorted(zip(cols, importance, strict=True), key=lambda t: -t[1])[:10]
    return AdversarialResult(
        auc=auc,
        top_features=[(c, float(i)) for c, i in pairs],
        n_train=len(X_train),
        n_serve=len(X_serve),
    )
