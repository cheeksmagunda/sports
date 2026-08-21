"""Job 2 model-artifact loading and trained-head prediction.

Extracted from job2.py. Owns the picker artifact lookup (SHA-pinned pkl
under models/) and the D63/D69 quantile-head batch prediction. Every
failure path returns None / empty so the caller's prediction ladder
falls through to its next tier instead of crashing the freeze.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from wnba_oracle.common.logging import get_logger
from wnba_oracle.features.spec import cohort_for_position
from wnba_oracle.scheduler.job2_scoring import _features_dict
from wnba_oracle.train.pipeline import PickerArtifact, load_artifact

log = get_logger("oracle.job2")

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_model_artifact(sha: str) -> PickerArtifact | None:
    """Load the trained PickerArtifact whose SHA256 matches `sha`.

    Looks under `models/` for any `picker_*.pkl` whose sidecar
    `.sha256` file matches. Returns None on any failure (missing,
    SHA mismatch, unpickle error) -- the caller falls back to the
    transparent heuristic.

    Empty `sha` short-circuits to None so deployments without the
    env var set behave exactly like the pre-D45 heuristic-only path.
    """
    if not sha:
        return None
    sha = sha.strip().lower()
    models_dir = REPO_ROOT / "models"
    if not models_dir.exists():
        log.warning("model_artifact_dir_missing", dir=str(models_dir))
        return None
    # `write_artifact` writes the sidecar at `picker_<commit>_<ts>.sha256`
    # (path.with_suffix(".sha256") REPLACES `.pkl`, it doesn't append).
    for sidecar in models_dir.glob("picker_*.sha256"):
        try:
            disk_sha = sidecar.read_text().strip().lower()
        except OSError:
            continue
        if disk_sha != sha:
            continue
        pkl_path = sidecar.with_suffix(".pkl")
        if not pkl_path.exists():
            log.warning("model_artifact_pkl_missing", path=str(pkl_path))
            return None
        try:
            art = load_artifact(pkl_path)
        except Exception as exc:
            log.exception("model_artifact_load_failed", path=str(pkl_path), error=str(exc))
            return None
        if not isinstance(art, PickerArtifact):
            log.error(
                "model_artifact_type_invalid",
                path=str(pkl_path),
                actual_type=type(art).__name__,
            )
            return None
        log.info(
            "model_artifact_loaded",
            path=str(pkl_path),
            sha=sha[:12],
            training_rows=art.training_rows,
            low_data_mode=art.low_data_mode,
            n_heads=len(art.heads),
            has_eb_baseline=art.eb_baseline is not None,
            n_eb_players=len(art.eb_baseline.player_alpha) if art.eb_baseline else 0,
        )
        return art
    log.warning("model_artifact_sha_not_found", sha=sha[:12])
    return None


def _eb_predict_one(art: PickerArtifact | None, player_id: int, position: str) -> float | None:
    """Single-player EB prediction with cohort + player-alpha lookup.

    Returns None if (a) no artifact, (b) no EB baseline in artifact, or
    (c) player_id wasn't seen in training. Caller falls back to the
    heuristic on None -- this preserves graceful degradation for new
    players the model never saw. The `team_pace` term is dropped
    because job1_enrichment doesn't yet carry team pace.
    """
    if art is None or art.eb_baseline is None:
        return None
    eb = art.eb_baseline
    if int(player_id) not in eb.player_alpha:
        return None
    cohort = cohort_for_position(position)
    mu = eb.cohort_means.get(cohort, 0.0)
    alpha = eb.player_alpha[int(player_id)]
    pred = mu + alpha
    return max(0.5, float(pred))


def _predict_heads_for_pool(
    art: PickerArtifact | None,
    enrichment: list[dict],
) -> dict[int, dict[str, float]]:
    """D69 / Phase 2b Tier-0: run the D63 trained heads over every pool player
    whose `head_features` row Job 1 persisted into ``features_json``.

    Returns {pid: {"p10", "p50", "p90"}} for matched players. Empty dict on:
      - artifact None / no minutes head trained (no behavioural change)
      - no pool player has head_features (cold-start day, fall through to ladder)
      - any predict failure (logged + skipped, per-player ladder still fires)
    """
    if art is None:
        return {}
    # Require both heads the recompose uses; otherwise predict_real_score returns
    # None and we save the import + frame build.
    minutes_head = art.heads.get(("minutes", "F"))
    rate_head = art.heads.get(("real_score_per_min", "F"))
    if minutes_head is None or rate_head is None:
        return {}
    feature_cols = minutes_head.feature_columns
    rate_cols = rate_head.feature_columns
    # The two heads were trained on identical _BASE_FEATURES (features/spec.py).
    # Take the union so neither booster sees a missing column at predict time.
    needed = tuple(dict.fromkeys((*feature_cols, *rate_cols)))

    pids: list[int] = []
    rows: list[dict] = []
    for r in enrichment:
        pid_raw = r.get("real_sports_player_id")
        if pid_raw is None:
            continue
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            continue
        f = _features_dict(r.get("features_json"))
        hf = f.get("head_features") if isinstance(f, dict) else None
        if not isinstance(hf, dict) or not hf:
            continue
        # Cohort routing inside predict_real_score reads `position`; pool into "F"
        # for now (matches features/corpus build_gamelog_corpus, D63 memory).
        row: dict[str, object] = {"position": "F"}
        for c in needed:
            v = hf.get(c, 0.0)
            try:
                row[c] = float(v) if v is not None else 0.0
            except (TypeError, ValueError):
                row[c] = 0.0
        pids.append(pid)
        rows.append(row)
    if not rows:
        return {}
    try:
        import polars as pl

        frame = pl.DataFrame(rows)
        pred = art.predict_real_score(frame)
    except Exception as exc:
        log.warning("head_predict_failed", reason=str(exc)[:160])
        return {}
    if pred is None:
        return {}
    out: dict[int, dict[str, float]] = {}
    for pid, p10, p50, p90 in zip(pids, pred["p10"], pred["p50"], pred["p90"]):
        if p50 is None or not np.isfinite(p50):
            continue
        out[int(pid)] = {
            "p10": float(p10) if np.isfinite(p10) else 0.0,
            "p50": float(p50),
            "p90": float(p90) if np.isfinite(p90) else float(p50),
        }
    log.info("head_predict", n_in=len(rows), n_out=len(out))
    return out
