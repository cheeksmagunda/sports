"""Model shadow-eval: run a challenger head over the same enrichment as
the champion and log a ``model_shadow_runs`` row for the rotation gate.

The prod freeze is untouched; the challenger is loaded only when
WNBA_ORACLE_MODEL_CHALLENGER_SHA is set on the environment. Failures
here never break job2 -- the whole call is guarded by the caller's
except and the writer swallows everything below the top of run().

Row schema (existing ``model_shadow_runs`` table):

    slate_date, challenger_sha, incumbent_sha, rbo_at_5, ndcg_at_5,
    realized_value_delta, payload_json (top-5 pid lists per model)

``realized_value_delta`` starts NULL and is filled at dayclose once
``slate_labels.real_score`` is available for the players in either
top-5. Positive = challenger's top-5 outscored the champion's.
"""

from __future__ import annotations

import hashlib
import json as _json
import math
from dataclasses import dataclass

from sqlalchemy import text

from wnba_oracle.common.logging import get_logger
from wnba_oracle.db.engine import get_engine
from wnba_oracle.scheduler.job2_scoring import _features_dict

log = get_logger("oracle.shadow")


SHADOW_INSERT = text(
    """
    INSERT INTO model_shadow_runs (
        slate_date, challenger_sha, incumbent_sha,
        rbo_at_5, ndcg_at_5, realized_value_delta, payload_json, created_at
    ) VALUES (
        :sd, :ch, :inc, :rbo, :ndcg, NULL, CAST(:payload AS JSONB), now()
    )
    ON CONFLICT ON CONSTRAINT uq_shadow_slate_challenger DO NOTHING
    """
)

# Backfill target: rows we wrote at freeze time with realized_value_delta=NULL.
SHADOW_PENDING_Q = text(
    """
    SELECT slate_date::text AS slate_date, challenger_sha, incumbent_sha, payload_json
    FROM model_shadow_runs
    WHERE realized_value_delta IS NULL
      AND slate_date >= :since
    """
)

SHADOW_UPDATE_DELTA = text(
    """
    UPDATE model_shadow_runs
    SET realized_value_delta = :delta,
        payload_json = CAST(:payload AS JSONB)
    WHERE slate_date = :sd AND challenger_sha = :ch
    """
)


@dataclass(frozen=True)
class ShadowResult:
    slate_date: str
    incumbent_sha: str
    challenger_sha: str
    incumbent_top5: list[int]
    challenger_top5: list[int]
    rbo_at_5: float
    ndcg_at_5: float


def _score_rank(
    head_predictions: dict[int, dict[str, float]], boost_by_pid: dict[int, float]
) -> list[int]:
    """Order pids by ``pred_p50 * (2.0 + card_boost)`` desc.

    Matches the picker's stage-1 filter (``MAX_SLOT_MULT + boost``) so
    the rank reflects the same "ceiling contribution" metric the
    optimizer prioritizes. Pids with no p50 in the predictions dict are
    dropped (challenger didn't produce a projection).
    """
    scored: list[tuple[int, float]] = []
    for pid, pred in head_predictions.items():
        p50 = pred.get("p50")
        if p50 is None or not math.isfinite(float(p50)):
            continue
        boost = float(boost_by_pid.get(int(pid), 0.0))
        scored.append((int(pid), float(p50) * (2.0 + boost)))
    scored.sort(key=lambda t: t[1], reverse=True)
    return [pid for pid, _ in scored]


def _rbo_at_k(a: list[int], b: list[int], k: int = 5, p: float = 0.9) -> float:
    """Rank-Biased Overlap at depth k. Same simplified form the rotation
    gate uses (audit/rotation_cli.py); duplicated here so shadow writes
    do not import the audit package."""
    a, b = a[:k], b[:k]
    if not a or not b:
        return 0.0
    score = 0.0
    seen_a: set[int] = set()
    seen_b: set[int] = set()
    for d in range(1, k + 1):
        seen_a.update(a[:d])
        seen_b.update(b[:d])
        score += (p ** (d - 1)) * (len(seen_a & seen_b) / d)
    return (1 - p) * score / (1 - p**k)


def _ndcg_at_k(ranking_pred: list[int], reference: list[int], k: int = 5) -> float:
    """NDCG@k treating ``reference`` (incumbent's top-k) as the graded-relevance
    ground truth: reference[0] gets relevance k, reference[k-1] gets 1, others 0.
    Equal ranks -> NDCG=1. Empty inputs -> 0.

    Not the classical relevance definition (that's slate-outcome-driven),
    but it's the metric the rotation-gate CLI expects and a workable
    proxy for "how similar are the two top-lists.
    """
    if not ranking_pred or not reference:
        return 0.0
    rel: dict[int, float] = {pid: float(k - i) for i, pid in enumerate(reference[:k])}
    dcg = sum(rel.get(pid, 0.0) / math.log2(i + 2) for i, pid in enumerate(ranking_pred[:k]))
    ideal = sum(rel[pid] / math.log2(i + 2) for i, pid in enumerate(reference[:k]) if pid in rel)
    return dcg / ideal if ideal > 0 else 0.0


def compute_shadow(
    slate_date: str,
    *,
    incumbent_sha: str,
    challenger_sha: str,
    incumbent_head: dict[int, dict[str, float]],
    challenger_head: dict[int, dict[str, float]],
    boost_by_pid: dict[int, float],
) -> ShadowResult | None:
    """Pure metric compute. Returns None when either ranking is empty."""
    inc_rank = _score_rank(incumbent_head, boost_by_pid)
    ch_rank = _score_rank(challenger_head, boost_by_pid)
    if not inc_rank or not ch_rank:
        return None
    return ShadowResult(
        slate_date=slate_date,
        incumbent_sha=incumbent_sha,
        challenger_sha=challenger_sha,
        incumbent_top5=inc_rank[:5],
        challenger_top5=ch_rank[:5],
        rbo_at_5=_rbo_at_k(ch_rank, inc_rank, k=5),
        ndcg_at_5=_ndcg_at_k(ch_rank, inc_rank, k=5),
    )


def persist_shadow(result: ShadowResult) -> None:
    """Idempotent insert -- (slate_date, challenger_sha) is unique in
    ``model_shadow_runs``. ON CONFLICT DO NOTHING so a second freeze
    fire in the same window is a no-op."""
    eng = get_engine()
    payload = _json.dumps(
        {
            "incumbent_top5": result.incumbent_top5,
            "challenger_top5": result.challenger_top5,
        }
    )
    with eng.begin() as conn:
        conn.execute(
            SHADOW_INSERT,
            {
                "sd": result.slate_date,
                "ch": result.challenger_sha,
                "inc": result.incumbent_sha,
                "rbo": result.rbo_at_5,
                "ndcg": result.ndcg_at_5,
                "payload": payload,
            },
        )
    log.info(
        "shadow_run_written",
        slate_date=result.slate_date,
        incumbent=result.incumbent_sha[:12],
        challenger=result.challenger_sha[:12],
        rbo=result.rbo_at_5,
        ndcg=result.ndcg_at_5,
    )


def _realized_delta_from_scores(
    incumbent_top5: list[int],
    challenger_top5: list[int],
    real_score_by_pid: dict[int, float],
) -> float:
    """Sum of realized ``real_score`` for the challenger's top-5 minus the
    incumbent's, using the SAME slate's slate_labels. Pids without a
    label are treated as 0 (they didn't play / weren't captured). This
    is unweighted by card_boost / slot_mult on purpose: the rotation gate
    is measuring head-prediction quality, not lineup construction."""
    inc = sum(float(real_score_by_pid.get(int(p), 0.0)) for p in incumbent_top5)
    ch = sum(float(real_score_by_pid.get(int(p), 0.0)) for p in challenger_top5)
    return ch - inc


def backfill_realized_value_delta(*, days_back: int = 30) -> int:
    """Fill ``realized_value_delta`` for shadow rows whose slate now has
    slate_labels. Called from dayclose after label ingest. Returns the
    number of rows updated. Idempotent: a row that already has a delta
    is skipped by the WHERE clause."""
    from datetime import date, timedelta

    since = (date.today() - timedelta(days=days_back)).isoformat()
    eng = get_engine()
    n_updated = 0
    with eng.begin() as conn:
        pending = conn.execute(SHADOW_PENDING_Q, {"since": since}).fetchall()
        for row in pending:
            sd = row._mapping["slate_date"]
            ch = row._mapping["challenger_sha"]
            payload = row._mapping["payload_json"]
            payload_dict = payload if isinstance(payload, dict) else _json.loads(payload or "{}")
            inc_top5 = [int(x) for x in payload_dict.get("incumbent_top5") or []]
            ch_top5 = [int(x) for x in payload_dict.get("challenger_top5") or []]
            if not inc_top5 or not ch_top5:
                continue
            # slate_labels: only players with a realized real_score.
            labels = conn.execute(
                text(
                    "SELECT platform_player_id, real_score FROM slate_labels "
                    "WHERE slate_date = :sd AND real_score IS NOT NULL"
                ),
                {"sd": sd},
            ).fetchall()
            if not labels:
                continue
            rs_by_pid = {
                int(r._mapping["platform_player_id"]): float(r._mapping["real_score"] or 0.0)
                for r in labels
            }
            delta = _realized_delta_from_scores(inc_top5, ch_top5, rs_by_pid)
            enriched = {
                **payload_dict,
                "incumbent_top5_scores": [rs_by_pid.get(p, 0.0) for p in inc_top5],
                "challenger_top5_scores": [rs_by_pid.get(p, 0.0) for p in ch_top5],
            }
            conn.execute(
                SHADOW_UPDATE_DELTA,
                {
                    "sd": sd,
                    "ch": ch,
                    "delta": delta,
                    "payload": _json.dumps(enriched),
                },
            )
            n_updated += 1
    if n_updated:
        log.info("shadow_realized_backfill", n_updated=n_updated, since=since)
    return n_updated


def _maybe_run_shadow(
    slate_date: str,
    enrichment: list[dict],
    incumbent_sha: str,
    incumbent_head: dict[int, dict[str, float]],
    boost_by_pid: dict[int, float],
    challenger_sha: str,
) -> None:
    """Load the challenger, run its heads, write the row. Guarded so any
    failure logs and returns cleanly -- prod freeze must never depend on
    the shadow path."""
    if not challenger_sha:
        return
    if challenger_sha.strip().lower() == (incumbent_sha or "").strip().lower():
        log.info(
            "shadow_skipped_same_sha",
            slate_date=slate_date,
            note="challenger sha matches incumbent; nothing to shadow",
        )
        return
    try:
        # Local import defers the (heavy) sklearn/polars pull until a
        # challenger is actually configured. Same reason job2.py defers
        # its head imports.
        from wnba_oracle.scheduler.job2 import _load_model_artifact, _predict_heads_for_pool

        ch_art = _load_model_artifact(challenger_sha)
        if ch_art is None:
            log.warning(
                "shadow_challenger_unresolved",
                slate_date=slate_date,
                challenger=challenger_sha[:12],
            )
            return
        ch_head = _predict_heads_for_pool(ch_art, enrichment)
        if not ch_head:
            log.warning(
                "shadow_challenger_empty_head",
                slate_date=slate_date,
                challenger=challenger_sha[:12],
                note="head predict returned empty -- pool lacks head_features",
            )
            return
        result = compute_shadow(
            slate_date,
            incumbent_sha=incumbent_sha,
            challenger_sha=challenger_sha,
            incumbent_head=incumbent_head,
            challenger_head=ch_head,
            boost_by_pid=boost_by_pid,
        )
        if result is None:
            return
        persist_shadow(result)
    except Exception as exc:
        log.warning(
            "shadow_run_failed",
            slate_date=slate_date,
            challenger=challenger_sha[:12],
            reason=str(exc)[:160],
        )


# 2026-07-04 knob shadow -----------------------------------------------------
#
# The model shadow above compares two head artifacts; this one compares two
# picker knob configurations against the SAME artifact. Because the schema
# uniqueness key is (slate_date, challenger_sha), we synthesize a stable
# challenger_sha keyed on the overlay JSON so the knob-shadow row coexists
# with any model-shadow row on the same slate.

_KNOB_SHADOW_PREFIX = "knob_"

_KNOB_DEFAULTS: dict[str, object] = {
    "starter_unknown_fade": 1.0,
    "picker_boost_tail_lift": False,
    "boost_tail_lift_threshold": 2.0,
    "boost_tail_lift_factor": 1.5,
}


def _overlay_challenger_sha(overlay: dict) -> str:
    """Stable per-overlay pseudo-sha so ON CONFLICT dedup is per-config,
    not per-slate. The prefix marks the row as a knob shadow so the
    rotation-gate CLI can tell it apart from model shadows."""
    canonical = _json.dumps(overlay, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    return f"{_KNOB_SHADOW_PREFIX}{digest}"


def _apply_knob_overlay(
    p50: float,
    boost: float,
    features: dict,
    overlay: dict,
) -> float:
    """Return the challenger stage-1 rank score for a single pool player.

    Mirrors src/wnba_oracle/scheduler/job2.py:572 (head-served path):
        pred_real_score = p50 * starter_mult
        rank_pred       = pred_real_score, unless boost >= threshold and
                          boost_tail_lift is on -- then p50 is multiplied
                          by lift_factor first.

    Only the stage-1 filter portion is reproduced here -- gs_mult and
    prop_mult are neutral in the overlay path (they still apply upstream
    identically for incumbent and challenger, so they cancel in the RBO/NDCG
    ordering).
    """
    fade = float(overlay.get("starter_unknown_fade", _KNOB_DEFAULTS["starter_unknown_fade"]))
    lift_on = bool(overlay.get("picker_boost_tail_lift", _KNOB_DEFAULTS["picker_boost_tail_lift"]))
    lift_thresh = float(
        overlay.get("boost_tail_lift_threshold", _KNOB_DEFAULTS["boost_tail_lift_threshold"])
    )
    lift_factor = float(
        overlay.get("boost_tail_lift_factor", _KNOB_DEFAULTS["boost_tail_lift_factor"])
    )
    is_starter = int(features.get("is_starter", 0) or 0)
    rotowire_confirmed = int(features.get("rotowire_confirmed", 0) or 0)
    if is_starter == 0 and rotowire_confirmed == 0:
        starter_mult = fade
    elif rotowire_confirmed == 1 and is_starter == 0:
        starter_mult = 0.82
    else:
        starter_mult = 1.10
    center = p50 * lift_factor if (lift_on and boost >= lift_thresh) else p50
    return max(0.5, center * starter_mult)


def _rank_with_overlay(
    head_predictions: dict[int, dict[str, float]],
    boost_by_pid: dict[int, float],
    features_by_pid: dict[int, dict],
    overlay: dict,
) -> list[int]:
    """Order pids by challenger stage-1 rank score * (2 + card_boost). Same
    (MAX_SLOT_MULT + boost) factor the picker uses in optimize.py."""
    from wnba_oracle.picker.optimize import MAX_SLOT_MULT

    scored: list[tuple[int, float]] = []
    for pid, pred in head_predictions.items():
        p50 = pred.get("p50")
        if p50 is None or not math.isfinite(float(p50)):
            continue
        boost = float(boost_by_pid.get(int(pid), 0.0))
        features = features_by_pid.get(int(pid), {})
        rank = _apply_knob_overlay(float(p50), boost, features, overlay)
        scored.append((int(pid), rank * (MAX_SLOT_MULT + boost)))
    scored.sort(key=lambda t: t[1], reverse=True)
    return [pid for pid, _ in scored]


def _maybe_run_knob_shadow(
    slate_date: str,
    enrichment: list[dict],
    incumbent_sha: str,
    incumbent_head: dict[int, dict[str, float]],
    boost_by_pid: dict[int, float],
    overlay_json: str,
) -> None:
    """Log a knob-only shadow row: same model artifact on both sides, but the
    challenger applies ``overlay_json`` at the stage-1 ranker. Guarded so any
    failure logs and returns; the prod freeze must never depend on this path.

    Row shape: incumbent_sha = model artifact SHA, challenger_sha =
    knob_<hash>, payload_json = {incumbent_top5, challenger_top5, overlay}.
    Dayclose's ``backfill_realized_value_delta`` fills the realized delta
    once ``slate_labels`` finalize -- the same routine used for model
    shadows, since it only reads top-5 pids from the payload.
    """
    if not overlay_json:
        return
    try:
        overlay = _json.loads(overlay_json)
        if not isinstance(overlay, dict):
            log.warning("knob_shadow_bad_overlay", note="expected JSON object")
            return
    except (_json.JSONDecodeError, TypeError) as exc:
        log.warning("knob_shadow_bad_overlay_json", reason=str(exc)[:120])
        return
    if not incumbent_head:
        return
    features_by_pid: dict[int, dict] = {}
    for r in enrichment:
        pid_raw = r.get("real_sports_player_id")
        if pid_raw is None:
            continue
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            continue
        features_by_pid[pid] = _features_dict(r.get("features_json"))
    # Incumbent = the LIVE picker knobs, derived from the current settings so
    # the shadow reflects what the freeze actually shipped (not a raw p50
    # baseline). Challenger = the overlay JSON, so the row measures the
    # effect of swapping one config for the other.
    from wnba_oracle.common.settings import get_settings

    settings = get_settings()
    incumbent_overlay = {
        "starter_unknown_fade": float(getattr(settings, "starter_unknown_fade", 1.0)),
        "picker_boost_tail_lift": bool(getattr(settings, "picker_boost_tail_lift", False)),
        "boost_tail_lift_threshold": float(getattr(settings, "boost_tail_lift_threshold", 2.0)),
        "boost_tail_lift_factor": float(getattr(settings, "boost_tail_lift_factor", 1.5)),
    }
    inc_rank = _rank_with_overlay(incumbent_head, boost_by_pid, features_by_pid, incumbent_overlay)
    ch_rank = _rank_with_overlay(incumbent_head, boost_by_pid, features_by_pid, overlay)
    if not inc_rank or not ch_rank:
        return
    challenger_sha = _overlay_challenger_sha(overlay)
    if set(inc_rank[:5]) == set(ch_rank[:5]) and inc_rank[:5] == ch_rank[:5]:
        # Identity overlay: nothing to shadow. Still log so the dashboard
        # sees a heartbeat, but skip the row insert.
        log.info(
            "knob_shadow_identity",
            slate_date=slate_date,
            challenger=challenger_sha[:12],
        )
        return
    result = ShadowResult(
        slate_date=slate_date,
        incumbent_sha=incumbent_sha,
        challenger_sha=challenger_sha,
        incumbent_top5=inc_rank[:5],
        challenger_top5=ch_rank[:5],
        rbo_at_5=_rbo_at_k(ch_rank, inc_rank, k=5),
        ndcg_at_5=_ndcg_at_k(ch_rank, inc_rank, k=5),
    )
    # Reuse persist_shadow, but stamp the overlay onto the payload so
    # rotate-check can differentiate knob shadows from model shadows.
    eng = get_engine()
    payload = _json.dumps(
        {
            "incumbent_top5": result.incumbent_top5,
            "challenger_top5": result.challenger_top5,
            "overlay": overlay,
            "incumbent_overlay": incumbent_overlay,
            "kind": "knob_shadow",
        }
    )
    try:
        with eng.begin() as conn:
            conn.execute(
                SHADOW_INSERT,
                {
                    "sd": result.slate_date,
                    "ch": result.challenger_sha,
                    "inc": result.incumbent_sha,
                    "rbo": result.rbo_at_5,
                    "ndcg": result.ndcg_at_5,
                    "payload": payload,
                },
            )
        log.info(
            "knob_shadow_written",
            slate_date=slate_date,
            incumbent=incumbent_sha[:12],
            challenger=challenger_sha[:12],
            rbo=result.rbo_at_5,
            ndcg=result.ndcg_at_5,
        )
    except Exception as exc:
        log.warning(
            "knob_shadow_run_failed",
            slate_date=slate_date,
            challenger=challenger_sha[:12],
            reason=str(exc)[:160],
        )
