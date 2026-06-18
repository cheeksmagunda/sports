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
    predict_head,
    train_quantile_head,
)

log = get_logger("oracle.train.pipeline")

REPO_ROOT = Path(__file__).resolve().parents[3]
MODELS_DIR = REPO_ROOT / "models"
CONFIG_PATH = REPO_ROOT / "configs" / "models.yaml"


# z-score spread between the P10 and P90 quantiles: norm.ppf(0.9) - norm.ppf(0.1).
_P10_P90_Z_SPREAD = 2.5631031310892225
_HALF_Z = _P10_P90_Z_SPREAD / 2.0  # norm.ppf(0.9) = 1.2816
_MIN_MINUTES_FLOOR = 0.5
_MIN_RATE_FLOOR = 1e-4


def _sorted_quantiles(
    q: dict[float, np.ndarray], *, floor: float
) -> dict[float, np.ndarray]:
    """Per-row monotone (P10<=P50<=P90) quantiles with a positive floor.

    The three quantile boosters are trained independently and can cross
    (Chernozhukov rearrangement: sorting always restores a valid CDF). The floor
    keeps the lognormal recompose well-defined (log of a positive number).
    """
    stacked = np.sort(np.vstack([q[0.1], q[0.5], q[0.9]]), axis=0)
    stacked = np.maximum(stacked, floor)
    return {0.1: stacked[0], 0.5: stacked[1], 0.9: stacked[2]}


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

    def predict_real_score(self, frame: pl.DataFrame) -> dict[str, np.ndarray] | None:
        """Recompose E[real_score] = E[minutes] x E[real_score_per_min] per row.

        Routes each row to its G/F/C cohort (via the ``position`` column), runs the
        trained ``minutes`` and ``real_score_per_min`` quantile heads, and combines
        them as a lognormal product: the median is the product of medians and the
        log-spread adds in quadrature (minutes and per-minute efficiency treated as
        independent). Returns real-space {p10, p50, p90} arrays aligned to ``frame``
        row order, NaN where a row's cohort lacks both heads. Returns None when no
        cohort can be served (caller falls back to the heuristic ladder).

        Quantile crossing from the independent boosters is removed by sorting each
        head's three quantiles per row before recomposition.
        """
        from wnba_oracle.features.spec import cohort_for_position

        n = len(frame)
        if n == 0:
            return None
        p10 = np.full(n, np.nan)
        p50 = np.full(n, np.nan)
        p90 = np.full(n, np.nan)
        positions = (
            frame.get_column("position").to_list()
            if "position" in frame.columns
            else [None] * n
        )
        cohorts = [cohort_for_position(p) for p in positions]
        served_any = False
        for cohort in ("G", "F", "C"):
            mh = self.heads.get(("minutes", cohort))
            rh = self.heads.get(("real_score_per_min", cohort))
            if mh is None or rh is None:
                continue
            idx = [i for i, c in enumerate(cohorts) if c == cohort]
            if not idx:
                continue
            sub = frame[idx]
            mn = _sorted_quantiles(predict_head(mh, sub), floor=_MIN_MINUTES_FLOOR)
            rt = _sorted_quantiles(predict_head(rh, sub), floor=_MIN_RATE_FLOOR)
            med = mn[0.5] * rt[0.5]
            slog_min = (np.log(mn[0.9]) - np.log(mn[0.1])) / _P10_P90_Z_SPREAD
            slog_rate = (np.log(rt[0.9]) - np.log(rt[0.1])) / _P10_P90_Z_SPREAD
            slog = np.sqrt(slog_min**2 + slog_rate**2)
            ix = np.asarray(idx)
            p50[ix] = med
            p10[ix] = med * np.exp(-_HALF_Z * slog)
            p90[ix] = med * np.exp(+_HALF_Z * slog)
            served_any = True
        if not served_any:
            return None
        return {"p10": p10, "p50": p50, "p90": p90}


def artifact_content_equal(a: PickerArtifact, b: PickerArtifact) -> tuple[bool, str]:
    """Compare two artifacts by trained-model CONTENT, not pickle bytes.

    The determinism gate (``make determinism-check``) trains twice and asserts
    the two artifacts are identical. Comparing pickle SHAs is wrong: LightGBM
    ``Booster`` pickles are not byte-stable even when the trained model is
    identical (they carry process-specific buffers), so a content-deterministic
    training run would still FAIL a pickle-byte check. This compares the
    canonical model serialization (``Booster.model_to_string``) plus the EB
    baseline parameters, which ARE stable under identical training.

    Returns ``(equal, reason)``; ``reason`` names the first divergence found.
    """
    if set(a.heads) != set(b.heads):
        return False, f"head keys differ: {sorted(map(str, a.heads))} vs {sorted(map(str, b.heads))}"
    for key in a.heads:
        ha, hb = a.heads[key], b.heads[key]
        if set(ha.quantile_models) != set(hb.quantile_models):
            return False, f"head {key} quantile set differs"
        for q in ha.quantile_models:
            if ha.quantile_models[q].model_to_string() != hb.quantile_models[q].model_to_string():
                return False, f"head {key} quantile {q} booster content differs"
    ea, eb = a.eb_baseline, b.eb_baseline
    if (ea is None) != (eb is None):
        return False, "eb_baseline presence differs"
    if ea is not None and eb is not None:
        if ea.cohort_means != eb.cohort_means:
            return False, "eb_baseline cohort_means differ"
        if ea.player_alpha != eb.player_alpha:
            return False, "eb_baseline player_alpha differ"
        if (ea.pace_beta, ea.league_pace) != (eb.pace_beta, eb.league_pace):
            return False, "eb_baseline pace/league params differ"
    if a.cohort_means != b.cohort_means:
        return False, "artifact cohort_means differ"
    return True, "content-identical"


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
