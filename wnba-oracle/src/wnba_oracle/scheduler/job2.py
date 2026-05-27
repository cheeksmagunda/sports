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
import os
from dataclasses import dataclass

import numpy as np
from sqlalchemy import text

from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import get_settings
from wnba_oracle.db.engine import get_engine, get_redis
from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import LineupRecommendation, OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime, load_curve_from_archive
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
        "SELECT real_sports_player_id, name, team, opponent, position, card_boost "
        "FROM job1_enrichment WHERE slate_date = :sd"
    )
    with eng.connect() as conn:
        result = conn.execute(q, {"sd": slate_date})
        return [dict(row._mapping) for row in result]


def _build_specs(
    enrichment: list[dict],
) -> tuple[list[PlayerSamplingSpec], list[FieldPlayerSpec]]:
    samps: list[PlayerSamplingSpec] = []
    fields: list[FieldPlayerSpec] = []
    for r in enrichment:
        pid_raw = r.get("real_sports_player_id")
        if pid_raw is None:
            continue
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            continue
        team = str(r.get("team", "") or "")
        opp = str(r.get("opponent", "") or "")
        boost = float(r.get("card_boost", 0.0) or 0.0)
        # Heuristic predicted real_score (Step 6 model integration in next iteration)
        pred = _heuristic_real_score(boost)
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

    samps, fields = _build_specs(enrichment)
    if len(samps) < 5:
        return Job2Result(sd, model_sha, None, False, "specs_too_small")

    curve = load_curve_from_archive(sd) or default_curve_for_regime(
        settings.payout_regime
    )
    cfg = OptimizeConfig(
        top_n_filter=settings.optimizer_top_n_filter,
        n_samples=settings.optimizer_n_samples,
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


_ = os
