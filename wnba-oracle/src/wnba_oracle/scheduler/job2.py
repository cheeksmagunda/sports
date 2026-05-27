"""Job 2: predict + freeze near tip. Redis SET NX + Postgres UPSERT.

Once the lineup freezes, it never re-rolls intra-day. The Redis key
`wnba.frozen.{slate_date}` is SET with NX + TTL=24h; if it already exists
this Job 2 invocation is a no-op (idempotent). The Postgres frozen_lineups
table is UPSERTed on (slate_date, model_sha).

Pipeline:
1. Read Job 1 enrichment from job1_enrichment table.
2. Load the model artifact (if WNBA_ORACLE_MODEL_ARTIFACT_SHA set + file
   exists). Else use the transparent heuristic picker (low-data fallback).
3. Build sampling/field specs for the optimizer.
4. Load payout curve (from archive if available, else default for regime).
5. Run optimize_lineup.
6. Freeze.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass

import numpy as np
from sqlalchemy import text

from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import get_settings
from wnba_oracle.db.engine import get_engine, get_redis
from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.game_script import GameScriptConfig, game_script_multiplier
from wnba_oracle.picker.optimize import LineupRecommendation, OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime, load_curve_from_archive
from wnba_oracle.picker.popularity import (
    ContrarianConfig,
    apply_contrarian_adjustment,
    estimate_draft_popularity,
    slate_labels_to_popularity,
)
from wnba_oracle.picker.sample import PlayerSamplingSpec

log = get_logger("oracle.job2")


@dataclass(frozen=True)
class Job2Result:
    slate_date: str
    model_sha: str
    recommendation: LineupRecommendation | None
    frozen: bool
    reason: str


def _heuristic_real_score(card_boost: float) -> float:
    """Transparent fallback used when no model artifact is loaded.

    Documented score = 15.0 * (1 + 0.2 * card_boost). Anchors:
    - WNBA per-slate Real Score historically lives in roughly [-10, 40]
      with the median around 12-15 for starters.
    - The 0.2 slope on card_boost rewards higher-boost players modestly
      without dominating the heuristic.
    """
    return 15.0 * (1.0 + 0.2 * card_boost)


def _load_enrichment(slate_date: str) -> list[dict]:
    eng = get_engine()
    q = text(
        "SELECT real_sports_player_id, name, team, opponent, position, "
        "card_boost, features_json "
        "FROM job1_enrichment WHERE slate_date = :sd"
    )
    with eng.connect() as conn:
        result = conn.execute(q, {"sd": slate_date})
        return [dict(row._mapping) for row in result]


def _vegas_from_features(features_json: object) -> tuple[float, float]:
    """Extract (vegas_total, vegas_spread) from the features_json JSONB.
    Returns (0.0, 0.0) when absent so the game-script multiplier degrades
    to neutral. psycopg returns JSONB as already-parsed dicts."""
    if not features_json:
        return 0.0, 0.0
    if isinstance(features_json, str):
        import json as _json

        try:
            features_json = _json.loads(features_json)
        except _json.JSONDecodeError:
            return 0.0, 0.0
    if not isinstance(features_json, dict):
        return 0.0, 0.0
    return (
        float(features_json.get("vegas_total", 0.0) or 0.0),
        float(features_json.get("vegas_spread", 0.0) or 0.0),
    )


def _load_measured_drafts(slate_date: str) -> dict[int, int]:
    """Pull the most recent draftStats.drafts counts from slate_labels for
    the slate. Empty if Job 2 is firing before any contest finalized
    (typical case pregame). Job 2 then falls back to the popularity
    estimator."""
    try:
        eng = get_engine()
    except RuntimeError:
        return {}
    q = text(
        "SELECT platform_player_id, MAX(drafts) AS drafts "
        "FROM slate_labels WHERE slate_date = :sd AND drafts IS NOT NULL "
        "GROUP BY platform_player_id"
    )
    with eng.connect() as conn:
        rows = conn.execute(q, {"sd": slate_date}).fetchall()
    out: dict[int, int] = {}
    for r in rows:
        m = r._mapping
        pid = m.get("platform_player_id")
        d = m.get("drafts")
        if pid is None or d is None:
            continue
        out[int(pid)] = int(d)
    return out


def _build_specs(
    enrichment: list[dict],
    *,
    slate_date: str,
    contrarian_cfg: ContrarianConfig | None = None,
) -> tuple[list[PlayerSamplingSpec], list[FieldPlayerSpec]]:
    """Build the (sampling, field) specs the optimizer reads.

    Applies the anti-popularity contrarian adjustment (basketball-main
    Finding 4) to the heuristic real_score. Popularity comes from
    measured `drafts` in slate_labels when available, else from the
    estimator (season ppg + big-market + slate size).
    """
    if contrarian_cfg is None:
        s = get_settings()
        contrarian_cfg = ContrarianConfig(
            enabled=s.contrarian_enabled, strength=s.contrarian_strength
        )
    if not enrichment:
        return [], []

    # Slate-size signal for the popularity estimator
    n_games_on_slate = len({str(r.get("team", "") or "") for r in enrichment if r.get("team")}) // 2
    n_games_on_slate = max(n_games_on_slate, 1)

    measured_drafts = _load_measured_drafts(slate_date)
    if measured_drafts:
        popularity_scores = slate_labels_to_popularity(measured_drafts)
        log.info("contrarian_using_measured", n_measured=len(popularity_scores))
    else:
        # Estimator fallback: use card_boost as a weak proxy for season_ppg
        # since we don't yet ingest per-player season stats. card_boost is
        # inverse to rolling Real Rating average, so 3.0 -> cold star,
        # 0.0 -> hot star. We invert it.
        popularity_scores = {}
        for r in enrichment:
            pid_raw = r.get("real_sports_player_id")
            if pid_raw is None:
                continue
            try:
                pid = int(pid_raw)
            except (TypeError, ValueError):
                continue
            boost = float(r.get("card_boost", 0.0) or 0.0)
            # Pseudo-ppg in [10, 22] from boost in [3, 0]
            pseudo_ppg = 10.0 + (3.0 - boost) * 4.0
            popularity_scores[pid] = estimate_draft_popularity(
                season_ppg=pseudo_ppg,
                team=str(r.get("team", "") or ""),
                n_games_on_slate=n_games_on_slate,
            )

    # First pass: per-player predicted real_score (heuristic) modulated by
    # the per-game game-script multiplier. The multiplier reads Vegas
    # total + spread from features_json (Job 1 persisted them). Games
    # with no Vegas signal degrade to a neutral 1.0x.
    pred_real_scores: dict[int, float] = {}
    rows_by_pid: dict[int, dict] = {}
    gs_cfg = GameScriptConfig()
    for r in enrichment:
        pid_raw = r.get("real_sports_player_id")
        if pid_raw is None:
            continue
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            continue
        boost = float(r.get("card_boost", 0.0) or 0.0)
        total, spread = _vegas_from_features(r.get("features_json"))
        gs_mult = (
            game_script_multiplier(total, spread, cfg=gs_cfg) if total > 0 else 1.0
        )
        pred_real_scores[pid] = _heuristic_real_score(boost) * gs_mult
        rows_by_pid[pid] = r

    # Apply contrarian adjustment
    adjusted = apply_contrarian_adjustment(
        pred_real_scores, popularity_scores, contrarian_cfg
    )

    samps: list[PlayerSamplingSpec] = []
    fields: list[FieldPlayerSpec] = []
    for pid, pred in adjusted.items():
        r = rows_by_pid[pid]
        team = str(r.get("team", "") or "")
        opp = str(r.get("opponent", "") or "")
        boost = float(r.get("card_boost", 0.0) or 0.0)
        K = 10.0
        mu_log = float(np.log(max(pred + K, 1.0)))
        samps.append(
            PlayerSamplingSpec(
                player_id=pid,
                team=team,
                opponent=opp,
                mu=mu_log,
                sigma=0.25,
                boost=boost,
            )
        )
        fields.append(
            FieldPlayerSpec(
                player_id=pid,
                pred_real_score=pred,
                card_boost=boost,
            )
        )
    return samps, fields


FROZEN_UPSERT = text(
    """
    INSERT INTO frozen_lineups (
        slate_date, model_sha, payout_regime, frozen_at, lineup,
        entry_recommendation, expected_payout, metadata_json
    ) VALUES (
        :slate_date, :model_sha, :payout_regime, now(), CAST(:lineup AS JSONB),
        :entry_recommendation, :expected_payout, CAST(:metadata_json AS JSONB)
    )
    ON CONFLICT (slate_date, model_sha) DO UPDATE SET
        lineup = EXCLUDED.lineup,
        entry_recommendation = EXCLUDED.entry_recommendation,
        expected_payout = EXCLUDED.expected_payout,
        metadata_json = EXCLUDED.metadata_json,
        frozen_at = now();
    """
)


def _freeze(
    slate_date: str,
    model_sha: str,
    rec: LineupRecommendation,
    payout_regime: str,
) -> bool:
    """Redis SET NX with TTL is the lock-once semantics. Postgres UPSERT
    persists the chosen lineup. Returns True if this invocation actually
    set the lock (was the first), False if a prior invocation already did."""
    rd = get_redis()
    key = f"wnba.frozen.{slate_date}"
    lock_acquired = bool(rd.set(key, model_sha, nx=True, ex=24 * 3600))
    eng = get_engine()
    payload = {
        "slate_date": slate_date,
        "model_sha": model_sha,
        "payout_regime": payout_regime,
        "lineup": json.dumps(
            {
                "player_ids": list(rec.player_ids),
                "slot_multipliers": list(rec.slot_multipliers),
                "lineup_score_p10": rec.lineup_score_p10,
                "lineup_score_p50": rec.lineup_score_p50,
                "lineup_score_p90": rec.lineup_score_p90,
            }
        ),
        "entry_recommendation": rec.entry_flag,
        "expected_payout": rec.expected_payout,
        "metadata_json": json.dumps({"lock_acquired": lock_acquired}),
    }
    with eng.begin() as conn:
        conn.execute(FROZEN_UPSERT, payload)
    return lock_acquired


def run(slate_date: str | None = None, *, dry_run: bool = False) -> Job2Result:
    settings = get_settings()
    sd = slate_date or dt.date.today().isoformat()
    model_sha = settings.model_artifact_sha or "heuristic-v1"

    log.info("job2_start", slate_date=sd, model_sha=model_sha)
    enrichment = _load_enrichment(sd)
    if len(enrichment) < 5:
        log.warning("job2_pool_too_small", n=len(enrichment))
        return Job2Result(sd, model_sha, None, False, "pool_too_small")

    samps, fields = _build_specs(enrichment, slate_date=sd)
    if len(samps) < 5:
        return Job2Result(sd, model_sha, None, False, "specs_too_small")

    curve = load_curve_from_archive(sd) or default_curve_for_regime(
        settings.payout_regime
    )
    cfg = OptimizeConfig(
        top_n_filter=settings.optimizer_top_n_filter,
        n_samples=settings.optimizer_n_samples,
        max_per_team=settings.optimizer_max_per_team,
    )
    rec = optimize_lineup(samps, fields, curve, cfg=cfg)
    log.info(
        "job2_optimizer_done",
        n_pool=len(samps),
        expected_payout=rec.expected_payout,
        entry_flag=rec.entry_flag,
    )
    if dry_run:
        return Job2Result(sd, model_sha, rec, False, "dry_run")
    frozen = _freeze(sd, model_sha, rec, curve.regime)
    return Job2Result(sd, model_sha, rec, frozen, "ok" if frozen else "lock_held_by_prior_fire")


def main() -> int:
    configure_logging("INFO")
    settings = get_settings()
    sd = dt.date.today().isoformat()
    try:
        result = run(sd, dry_run=settings.job2_dry_run)
    except Exception as exc:
        log.exception("job2_failed", error=str(exc))
        return 1
    if result.recommendation is None:
        return 0
    return 0
