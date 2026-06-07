"""R7 prerequisite: does a 4-component-per-min recompose beat the single
real_score_per_min head?

Walk-forward eval (train pre-2026, predict 2026 game-by-game):
- BASELINE = current `predict_real_score`: E[min] x E[real_score_per_min]
- CANDIDATE = component recompose:
    E[min] x [ w_pts*E[pts/min] + w_reb*E[reb/min] + w_ast*E[ast/min]
              + (w_stl+w_blk)/2 * E[stl_blk/min] + residual ]
  where the residual is the per-cohort mean of
    (real_score_per_min - sum_of_weighted_components)
  computed from the training corpus. The 4 components cover ~70% of
  real_score's box-line weight; the residual absorbs everything else
  (shooting volume/efficiency, turnovers, oreb/dreb).

Metrics: Pearson corr, MAE, RMSE, CRPS at the median, P10-P90 coverage.
Decision: ship the components recompose IFF it lifts corr by >= 0.02 AND
CRPS drops by >= 5% AND coverage stays within 0.05 of nominal 0.80.

Run with the laptop's read-only role (DATABASE_PUBLIC_URL must be set)
and any locally-cached PickerArtifact in models/.
"""

from __future__ import annotations

import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import polars as pl
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from wnba_oracle.common.db_utils import normalize_postgres_url  # noqa: E402
from wnba_oracle.db.reads import read_game_logs  # noqa: E402
from wnba_oracle.features.corpus import build_gamelog_corpus  # noqa: E402
from wnba_oracle.features.spec import cohort_for_position  # noqa: E402
from wnba_oracle.predict.scoring import REAL_SCORE_WEIGHTS  # noqa: E402
from wnba_oracle.train.lgbm_heads import predict_head  # noqa: E402

# Reuse the same quantile-spread constants as train/pipeline.py.
_P10_P90_Z_SPREAD = 2.5631031310892225
_HALF_Z = _P10_P90_Z_SPREAD / 2.0
_MIN_FLOOR = 0.5
_RATE_FLOOR = 1e-4

# 4-component weight roll-up. stl_blk is the SUM (stl+blk)/min, so its
# effective weight is the average of stl and blk weights.
W_PTS = REAL_SCORE_WEIGHTS["pts"]
W_REB = REAL_SCORE_WEIGHTS["reb"] + REAL_SCORE_WEIGHTS["oreb"] + REAL_SCORE_WEIGHTS["dreb"]
W_AST = REAL_SCORE_WEIGHTS["ast"]
W_STL_BLK = (REAL_SCORE_WEIGHTS["stl"] + REAL_SCORE_WEIGHTS["blk"]) / 2.0


def _engine() -> sa.Engine:
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")
    if not url:
        raise RuntimeError("set DATABASE_URL or DATABASE_PUBLIC_URL")
    return sa.create_engine(normalize_postgres_url(url), future=True, pool_pre_ping=True)


def _load_latest_artifact() -> object:
    candidates = sorted(
        (ROOT / "models").glob("picker_*_*.pkl"), key=lambda p: p.stat().st_mtime
    )
    if not candidates:
        raise FileNotFoundError("no models/picker_*.pkl on disk")
    art = pickle.loads(candidates[-1].read_bytes())
    print(f"artifact: {candidates[-1].name} heads={list(art.heads.keys())}")
    return art


def _sorted_quantiles(q: dict[float, np.ndarray], *, floor: float) -> dict[float, np.ndarray]:
    stacked = np.sort(np.vstack([q[0.1], q[0.5], q[0.9]]), axis=0)
    stacked = np.maximum(stacked, floor)
    return {0.1: stacked[0], 0.5: stacked[1], 0.9: stacked[2]}


def _component_residual_per_cohort(corpus: pl.DataFrame) -> dict[str, float]:
    """Per-cohort scalar residual: mean of
    (real_score_per_min - sum_of_weighted_components) on the corpus."""
    df = corpus.filter(pl.col("real_score_per_min").is_not_null()).with_columns(
        (
            pl.col("real_score_per_min")
            - W_PTS * pl.col("pts_per_min")
            - W_REB * pl.col("reb_per_min")
            - W_AST * pl.col("ast_per_min")
            - W_STL_BLK * pl.col("stl_blk_per_min")
        ).alias("_resid")
    )
    df = df.with_columns(
        pl.col("position").map_elements(cohort_for_position, return_dtype=pl.String).alias("_coh")
    )
    out: dict[str, float] = {}
    for coh in ("G", "F", "C"):
        sub = df.filter(pl.col("_coh") == coh)
        if sub.is_empty():
            continue
        out[coh] = float(sub.get_column("_resid").mean() or 0.0)
    return out


def _predict_single_head(
    art: object, frame: pl.DataFrame
) -> dict[str, np.ndarray] | None:
    """Mirrors PickerArtifact.predict_real_score (1-head recompose). Kept inline
    so we use the EXACT same path the audit measures."""
    return art.predict_real_score(frame)


def _predict_components(
    art: object,
    frame: pl.DataFrame,
    residual_by_cohort: dict[str, float],
) -> dict[str, np.ndarray] | None:
    """5-head recompose: E[min] x (weighted sum of 4 component rates + scalar residual).

    Returns {p10, p50, p90} aligned to `frame`. NaN where the cohort lacks
    one of the required heads. P10/P90 are recomposed by treating minutes
    and per-min as independent lognormals (same convention as the 1-head path).
    """
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
    served = False
    for cohort in ("G", "F", "C"):
        mh = art.heads.get(("minutes", cohort))
        pts_h = art.heads.get(("points_per_min", cohort))
        reb_h = art.heads.get(("reb_per_min", cohort))
        ast_h = art.heads.get(("ast_per_min", cohort))
        sb_h = art.heads.get(("stl_blk_per_min", cohort))
        if any(h is None for h in (mh, pts_h, reb_h, ast_h, sb_h)):
            continue
        idx = [i for i, c in enumerate(cohorts) if c == cohort]
        if not idx:
            continue
        sub = frame[idx]
        mn = _sorted_quantiles(predict_head(mh, sub), floor=_MIN_FLOOR)
        pts = _sorted_quantiles(predict_head(pts_h, sub), floor=_RATE_FLOOR)
        reb = _sorted_quantiles(predict_head(reb_h, sub), floor=_RATE_FLOOR)
        ast = _sorted_quantiles(predict_head(ast_h, sub), floor=_RATE_FLOOR)
        sb = _sorted_quantiles(predict_head(sb_h, sub), floor=_RATE_FLOOR)
        res = residual_by_cohort.get(cohort, 0.0)
        # Per-min predicted rate per quantile:
        rate_q = {}
        for q in (0.1, 0.5, 0.9):
            rate_q[q] = (
                W_PTS * pts[q]
                + W_REB * reb[q]
                + W_AST * ast[q]
                + W_STL_BLK * sb[q]
                + res
            )
        # Floor rate at a small positive so the lognormal recompose is defined.
        for q in (0.1, 0.5, 0.9):
            rate_q[q] = np.maximum(rate_q[q], _RATE_FLOOR)
        med = mn[0.5] * rate_q[0.5]
        slog_min = (np.log(mn[0.9]) - np.log(mn[0.1])) / _P10_P90_Z_SPREAD
        slog_rate = (np.log(rate_q[0.9]) - np.log(rate_q[0.1])) / _P10_P90_Z_SPREAD
        slog = np.sqrt(slog_min**2 + slog_rate**2)
        ix = np.asarray(idx)
        p50[ix] = med
        p10[ix] = med * np.exp(-_HALF_Z * slog)
        p90[ix] = med * np.exp(+_HALF_Z * slog)
        served = True
    if not served:
        return None
    return {"p10": p10, "p50": p50, "p90": p90}


def _crps_lognormal_3q(y: np.ndarray, p10: np.ndarray, p50: np.ndarray, p90: np.ndarray) -> float:
    """Crude CRPS proxy from 3 quantiles: pinball loss averaged across the three.
    Equal to the standard quantile-loss decomposition; lower is better.
    """
    losses: list[float] = []
    for q, pred in ((0.1, p10), (0.5, p50), (0.9, p90)):
        e = y - pred
        losses.append(float(np.mean(np.where(e >= 0, q * e, (q - 1) * e))))
    return float(np.mean(losses))


def main() -> int:
    eng = _engine()
    print("loading game logs...")
    gl = read_game_logs(engine=eng)
    print(f"  {len(gl)} rows, last_date={gl.get_column('game_date').max()}")
    print("building gamelog corpus (this takes ~30s)...")
    corpus = build_gamelog_corpus(gl, min_prior_games=1)
    print(f"  corpus rows={len(corpus)}")

    # Split: pre-2026 train, 2026 eval. Matches train/pipeline.py's walk-forward.
    pre = corpus.filter(pl.col("game_date") < "2026-01-01")
    eval_set = corpus.filter(pl.col("game_date") >= "2026-01-01").filter(
        pl.col("real_score").is_not_null()
    )
    print(f"  pre-2026 train rows={len(pre)} 2026 eval rows={len(eval_set)}")

    print("computing per-cohort component residual on the train corpus...")
    residual = _component_residual_per_cohort(pre)
    print(f"  residual_by_cohort={residual}")

    art = _load_latest_artifact()
    print("predicting on 2026 eval rows...")
    base = _predict_single_head(art, eval_set)
    cand = _predict_components(art, eval_set, residual)
    if base is None or cand is None:
        print("ERROR: one or both predictors returned None (missing heads). Abort.")
        return 1

    y = eval_set.get_column("real_score").to_numpy()
    mask = (
        np.isfinite(y)
        & np.isfinite(base["p50"]) & np.isfinite(cand["p50"])
    )
    y = y[mask]
    base = {k: v[mask] for k, v in base.items()}
    cand = {k: v[mask] for k, v in cand.items()}
    n = len(y)
    print(f"  n_eval after NaN drop: {n}")

    def _row(label: str, p: dict[str, np.ndarray]) -> dict:
        pred50 = p["p50"]
        corr = float(np.corrcoef(y, pred50)[0, 1])
        mae = float(np.mean(np.abs(y - pred50)))
        rmse = float(np.sqrt(np.mean((y - pred50) ** 2)))
        crps = _crps_lognormal_3q(y, p["p10"], pred50, p["p90"])
        cov = float(np.mean((y >= p["p10"]) & (y <= p["p90"])))
        return {"label": label, "corr": corr, "mae": mae, "rmse": rmse, "crps": crps, "p10_p90_coverage": cov}

    rows = [
        _row("baseline_1head", base),
        _row("candidate_components", cand),
    ]
    print("\n=== walk-forward results (pre-2026 train, 2026 eval) ===")
    print(f"  {'label':<24} {'corr':>7} {'mae':>7} {'rmse':>7} {'crps':>7} {'cov80':>7}")
    for r in rows:
        print(
            f"  {r['label']:<24} {r['corr']:>7.4f} {r['mae']:>7.3f} {r['rmse']:>7.3f} "
            f"{r['crps']:>7.4f} {r['p10_p90_coverage']:>7.3f}"
        )

    b, c = rows[0], rows[1]
    d_corr = c["corr"] - b["corr"]
    d_crps_pct = (c["crps"] - b["crps"]) / max(1e-9, b["crps"])
    d_cov = abs(c["p10_p90_coverage"] - 0.80)
    print()
    print(f"  delta_corr = {d_corr:+.4f}  (need >= +0.02)")
    print(f"  delta_crps_pct = {d_crps_pct:+.4%}  (need <= -5%)")
    print(f"  candidate_cov80_distance_from_nominal = {d_cov:.3f}  (need <= 0.05)")
    ship = (d_corr >= 0.02) and (d_crps_pct <= -0.05) and (d_cov <= 0.05)
    print(f"\n  decision: {'SHIP components' if ship else 'KEEP single head'}")

    out_path = ROOT / "research" / "internal" / "_components_vs_single_head.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "n_eval": n,
                "rows": rows,
                "decision_ship_components": bool(ship),
                "delta_corr": d_corr,
                "delta_crps_pct": d_crps_pct,
                "candidate_cov80_distance_from_nominal": d_cov,
                "residual_by_cohort": residual,
            },
            indent=2,
        )
    )
    print(f"\n  JSON: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
