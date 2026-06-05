"""Top-level training pipeline.

Trains six multi-task heads per cohort + EB baseline + Mondrian CQR
calibrator + adversarial validation. Output is a single artifact pickled
to models/picker_<commit>_<ts>.pkl, with a SHA-256 sidecar.

Determinism: numpy / lightgbm / python seeds pinned. OMP_NUM_THREADS=1
in the Makefile target. `assert_byte_equal_after_two_runs` is the gate.

If labeled rows < configs/models.yaml::low_data_mode.min_labeled_rows
(default 2000), the pipeline switches to fallback hyperparameters and
emits a warning. The serving picker reads this flag from the artifact
metadata and shows a transparent heuristic ranking instead of LightGBM
predictions until corpus grows.
"""

from __future__ import annotations

import hashlib
import pickle
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import yaml

from wnba_oracle.common.logging import get_logger
from wnba_oracle.features.parity import feature_module_sha
from wnba_oracle.features.spec import (
    HEAD_SPECS,
    Cohort,
    cohort_for_position,
    feature_columns_for_head,
)
from wnba_oracle.train.calibrators import PCHIPIsotonic
from wnba_oracle.train.eb_baseline import EBHierarchicalBaseline
from wnba_oracle.train.lgbm_heads import (
    LGBMHeadConfig,
    TrainedHead,
    train_quantile_head,
)

log = get_logger("oracle.train.pipeline")

REPO_ROOT = Path(__file__).resolve().parents[3]
MODELS_DIR = REPO_ROOT / "models"
CONFIG_PATH = REPO_ROOT / "configs" / "models.yaml"


@dataclass
class PickerArtifact:
    feature_module_sha: str
    config: dict
    heads: dict[tuple[str, Cohort], TrainedHead] = field(default_factory=dict)
    eb_baseline: EBHierarchicalBaseline | None = None
    calibrators: dict[tuple[str, Cohort], PCHIPIsotonic] = field(default_factory=dict)
    training_rows: int = 0
    low_data_mode: bool = False
    cohort_means: dict[str, float] = field(default_factory=dict)
    feature_subset_per_head: dict[tuple[str, Cohort], tuple[str, ...]] = field(default_factory=dict)


def _set_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def _load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


def _filter_cohort(df: pl.DataFrame, cohort: Cohort) -> pl.DataFrame:
    if "cohort" in df.columns:
        return df.filter(pl.col("cohort") == cohort)
    return df.with_columns(
        pl.col("position").map_elements(cohort_for_position, return_dtype=pl.String).alias(
            "cohort"
        )
    ).filter(pl.col("cohort") == cohort)


def train_picker(
    train_df: pl.DataFrame,
    valid_df: pl.DataFrame,
    *,
    label_train: pl.DataFrame | None = None,
    label_valid: pl.DataFrame | None = None,
    target_real_score: str = "real_score",
    target_minutes: str = "minutes_played",
) -> PickerArtifact:
    """Train the multi-task ensemble.

    ``train_df``/``valid_df`` are the *heads* frame (the dense per-player-game
    corpus with the head target columns; see features/corpus.build_gamelog_corpus).
    ``label_train``/``label_valid`` are the *contest-label* frame the EB baseline
    fits on (card_boost + real_score per player-slate). When the label frames are
    omitted they default to the heads frame, preserving the single-corpus
    behaviour for callers that pass one frame.
    """
    cfg = _load_config()
    if label_train is None:
        label_train = train_df
    seed = int(cfg.get("seeds", {}).get("numpy", 1729))
    _set_seeds(seed)

    low_data = len(train_df) < int(
        cfg.get("low_data_mode", {}).get("min_labeled_rows", 2000)
    )
    head_cfg = LGBMHeadConfig(
        num_leaves=int(cfg["lightgbm"]["num_leaves"]),
        min_data_in_leaf=int(cfg["lightgbm"]["min_data_in_leaf"]),
        learning_rate=float(cfg["lightgbm"]["learning_rate"]),
        feature_fraction=float(cfg["lightgbm"]["feature_fraction"]),
        bagging_fraction=float(cfg["lightgbm"]["bagging_fraction"]),
        bagging_freq=int(cfg["lightgbm"]["bagging_freq"]),
        lambda_l2=float(cfg["lightgbm"]["lambda_l2"]),
        min_gain_to_split=float(cfg["lightgbm"]["min_gain_to_split"]),
        num_boost_round=int(cfg["lightgbm"]["num_boost_round"]),
        early_stopping_rounds=int(cfg["lightgbm"]["early_stopping_rounds"]),
        seed=seed,
    )
    if low_data:
        fb = cfg.get("low_data_mode", {}).get("fallback_lightgbm", {}) or {}
        head_cfg = LGBMHeadConfig(
            num_leaves=int(fb.get("num_leaves", head_cfg.num_leaves)),
            min_data_in_leaf=head_cfg.min_data_in_leaf,
            learning_rate=head_cfg.learning_rate,
            feature_fraction=float(fb.get("feature_fraction", head_cfg.feature_fraction)),
            bagging_fraction=head_cfg.bagging_fraction,
            bagging_freq=head_cfg.bagging_freq,
            lambda_l2=float(fb.get("lambda_l2", head_cfg.lambda_l2)),
            min_gain_to_split=head_cfg.min_gain_to_split,
            num_boost_round=int(fb.get("num_boost_round", head_cfg.num_boost_round)),
            early_stopping_rounds=head_cfg.early_stopping_rounds,
            seed=seed,
        )
        log.warning("low_data_mode", n_train=len(train_df))

    monotone = cfg.get("monotone_constraints", {})
    art = PickerArtifact(
        feature_module_sha=feature_module_sha(),
        config=cfg,
        training_rows=len(train_df),
        low_data_mode=low_data,
    )

    cohorts: tuple[Cohort, ...] = ("G", "F", "C")
    for cohort in cohorts:
        c_train = _filter_cohort(train_df, cohort)
        c_valid = _filter_cohort(valid_df, cohort)
        if c_train.is_empty():
            log.warning("empty_cohort", cohort=cohort)
            continue
        for head_name, head_spec in HEAD_SPECS.items():
            target = head_spec.target
            if target not in c_train.columns:
                # Multi-task targets that the corpus doesn't yet expose
                # (per-min rates etc.) are skipped; predict-time recompose
                # uses the population mean as fallback.
                continue
            feat_cols = feature_columns_for_head(head_name, cohort)
            feat_cols = tuple(c for c in feat_cols if c in c_train.columns)
            if not feat_cols:
                continue
            cell_train = c_train.select([*feat_cols, target]).drop_nulls(target)
            cell_valid = (
                c_valid.select([*feat_cols, target]).drop_nulls(target)
                if not c_valid.is_empty() and target in c_valid.columns
                else pl.DataFrame()
            )
            if cell_train.is_empty():
                continue
            head = train_quantile_head(
                name=head_name,
                cohort=cohort,
                target=target,
                feature_columns=feat_cols,
                train_df=cell_train,
                valid_df=cell_valid,
                monotone_constraints=monotone,
                cfg=head_cfg,
            )
            art.heads[(head_name, cohort)] = head
            art.feature_subset_per_head[(head_name, cohort)] = feat_cols

            # PCHIP calibrator on the median quantile against the validation
            # set (or train set if no valid set).
            calib_src = cell_valid if not cell_valid.is_empty() else cell_train
            if not calib_src.is_empty():
                X = calib_src.select(list(feat_cols)).to_pandas()
                med = head.quantile_models[0.5]
                pred = np.asarray(med.predict(X), dtype=float)
                calib = PCHIPIsotonic()
                calib.fit(pred, calib_src.get_column(target).to_numpy())
                art.calibrators[(head_name, cohort)] = calib

    # EB baseline on the contest-label frame's real_score column (if present).
    if target_real_score in label_train.columns:
        eb = EBHierarchicalBaseline()
        eb_input = label_train.with_columns(
            pl.col("position").map_elements(cohort_for_position, return_dtype=pl.String).alias(
                "cohort"
            )
            if "cohort" not in train_df.columns
            else pl.col("cohort")
        )
        eb.fit(eb_input, target=target_real_score)
        art.eb_baseline = eb
        art.cohort_means = eb.cohort_means

    return art


def _git_sha_short() -> str:
    """Pinned alongside the artifact so reloads know the build commit."""
    import subprocess

    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return r.stdout.strip()[:12]
    except Exception:
        return "no-git"


def write_artifact(art: PickerArtifact, *, commit: str) -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    import time as _time

    ts = int(_time.time())
    path = MODELS_DIR / f"picker_{commit[:8]}_{ts}.pkl"
    payload = pickle.dumps(art, protocol=pickle.HIGHEST_PROTOCOL)
    path.write_bytes(payload)
    sha = hashlib.sha256(payload).hexdigest()
    (path.with_suffix(".sha256")).write_text(sha)
    log.info("artifact_written", path=str(path), sha256=sha)
    return path


def load_artifact(path: Path) -> PickerArtifact:
    payload = path.read_bytes()
    sha_path = path.with_suffix(".sha256")
    if sha_path.exists():
        expected = sha_path.read_text().strip()
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected:
            raise RuntimeError(
                f"artifact SHA mismatch for {path}: expected {expected}, got {actual}"
            )
    return pickle.loads(payload)
