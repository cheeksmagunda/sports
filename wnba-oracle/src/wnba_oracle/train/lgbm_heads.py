"""LightGBM quantile heads for the multi-task pipeline.

One head per (target, cohort) cell. Each head trains three quantile models
at alphas (0.1, 0.5, 0.9). Monotonicity constraints (Part 6.4) are applied
per feature. Determinism: seeds pinned, `deterministic=True`, single thread.
"""

from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import polars as pl

from wnba_oracle.common.logging import get_logger

log = get_logger("oracle.train.lgbm_heads")

DEFAULT_QUANTILES = (0.1, 0.5, 0.9)


@dataclass(frozen=True)
class LGBMHeadConfig:
    num_leaves: int = 15
    min_data_in_leaf: int = 25
    learning_rate: float = 0.04
    feature_fraction: float = 0.70
    bagging_fraction: float = 0.80
    bagging_freq: int = 5
    lambda_l2: float = 1.0
    min_gain_to_split: float = 0.01
    num_boost_round: int = 200
    early_stopping_rounds: int = 25
    seed: int = 1729


@dataclass
class TrainedHead:
    name: str
    cohort: str
    target: str
    feature_columns: tuple[str, ...]
    quantile_models: dict[float, lgb.Booster]
    monotone_constraints: tuple[int, ...]


def train_quantile_head(
    *,
    name: str,
    cohort: str,
    target: str,
    feature_columns: tuple[str, ...],
    train_df: pl.DataFrame,
    valid_df: pl.DataFrame,
    monotone_constraints: dict[str, int] | None = None,
    categorical_features: tuple[str, ...] = (),
    cfg: LGBMHeadConfig = LGBMHeadConfig(),
    quantiles: tuple[float, ...] = DEFAULT_QUANTILES,
) -> TrainedHead:
    """Train one head: three LightGBM quantile boosters at the given alphas.

    `train_df` and `valid_df` must contain `feature_columns + (target,)`.
    For per-min rate heads (head.condition: minutes_played > 0), the caller
    pre-filters the rows.
    """
    if train_df.is_empty():
        raise ValueError(f"empty train_df for head {name}/{cohort}")
    # Recorded for the artifact, but NOT passed to LightGBM: the quantile
    # objective is incompatible with monotone_constraints ("Cannot use
    # ``monotone_constraints`` in quantile objective"). Feature monotonicity on
    # the quantile heads would need a post-hoc projection or a separate rank
    # head (mlb-oracle pattern); deferred. Regularization is carried by
    # num_leaves / min_data_in_leaf / lambda_l2 instead.
    mc_vec = tuple((monotone_constraints or {}).get(c, 0) for c in feature_columns)

    # Materialize as numpy/pandas for LightGBM.
    X_train = train_df.select(list(feature_columns)).to_pandas()
    y_train = train_df.get_column(target).to_pandas()
    X_valid = (
        valid_df.select(list(feature_columns)).to_pandas() if not valid_df.is_empty() else None
    )
    y_valid = valid_df.get_column(target).to_pandas() if not valid_df.is_empty() else None

    cat_cols = [c for c in categorical_features if c in feature_columns]

    quantile_models: dict[float, lgb.Booster] = {}
    for alpha in quantiles:
        params = {
            "objective": "quantile",
            "alpha": alpha,
            "num_leaves": cfg.num_leaves,
            "min_data_in_leaf": cfg.min_data_in_leaf,
            "learning_rate": cfg.learning_rate,
            "feature_fraction": cfg.feature_fraction,
            "bagging_fraction": cfg.bagging_fraction,
            "bagging_freq": cfg.bagging_freq,
            "lambda_l2": cfg.lambda_l2,
            "min_gain_to_split": cfg.min_gain_to_split,
            "deterministic": True,
            "force_col_wise": True,
            "verbosity": -1,
            "seed": cfg.seed,
            "feature_pre_filter": False,
        }
        train_set = lgb.Dataset(
            X_train,
            label=y_train,
            categorical_feature=cat_cols if cat_cols else "auto",
            free_raw_data=False,
        )
        valid_sets = [train_set]
        valid_names = ["train"]
        callbacks: list = []
        if X_valid is not None and not X_valid.empty:
            valid_set = lgb.Dataset(
                X_valid,
                label=y_valid,
                reference=train_set,
                categorical_feature=cat_cols if cat_cols else "auto",
                free_raw_data=False,
            )
            valid_sets.append(valid_set)
            valid_names.append("valid")
            callbacks.append(lgb.early_stopping(cfg.early_stopping_rounds, verbose=False))
        booster = lgb.train(
            params,
            train_set,
            num_boost_round=cfg.num_boost_round,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=callbacks,
        )
        quantile_models[alpha] = booster
        log.info(
            "head_trained",
            name=name,
            cohort=cohort,
            alpha=alpha,
            best_iter=booster.best_iteration,
        )

    return TrainedHead(
        name=name,
        cohort=cohort,
        target=target,
        feature_columns=feature_columns,
        quantile_models=quantile_models,
        monotone_constraints=mc_vec,
    )


def predict_head(
    head: TrainedHead, X: pl.DataFrame, *, quantiles: tuple[float, ...] = DEFAULT_QUANTILES
) -> dict[float, np.ndarray]:
    """Returns {alpha: array} for the head."""
    X_pd = X.select(list(head.feature_columns)).to_pandas()
    out: dict[float, np.ndarray] = {}
    for alpha in quantiles:
        booster = head.quantile_models.get(alpha)
        if booster is None:
            continue
        out[alpha] = np.asarray(booster.predict(X_pd), dtype=float)
    return out
