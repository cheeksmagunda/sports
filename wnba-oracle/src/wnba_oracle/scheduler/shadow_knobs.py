"""Knob-overlay shadow harness (2026-07-04, follow-up to model shadow D95).

Extracted from shadow.py. Where the model shadow compares two head
artifacts, this compares two picker knob configurations against the
SAME artifact: the incumbent's head predictions replayed through a
hypothetical overlay, logging a ``model_shadow_runs`` row so dayclose
can backfill the realized delta the same way it does for model shadows.

Because the schema uniqueness key is (slate_date, challenger_sha), the
challenger_sha is synthesized from a hash of the overlay JSON so a knob
shadow row coexists with any model-shadow row on the same slate.
"""

from __future__ import annotations

import hashlib
import json as _json
import math

from wnba_oracle.common.logging import get_logger
from wnba_oracle.db.engine import get_engine
from wnba_oracle.scheduler.job2_scoring import _features_dict
from wnba_oracle.scheduler.shadow import (
    SHADOW_INSERT,
    ShadowResult,
    _ndcg_at_k,
    _rbo_at_k,
)

log = get_logger("oracle.shadow")

_KNOB_SHADOW_PREFIX = "knob_"

_KNOB_DEFAULTS: dict[str, object] = {
    "starter_unknown_fade": 1.0,
    "picker_boost_tail_lift": False,
    "boost_tail_lift_threshold": 2.0,
    "boost_tail_lift_factor": 1.5,
    # 2026-07-10 suite: minutes-conditional starter lift + mid-slot floor tilt.
    "starter_minutes_lift_enabled": False,
    "starter_minutes_norm": 25.0,
    "starter_minutes_lift_weight": 0.6,
    "starter_minutes_lift_cap": 1.3,
    "floor_tilt_weight": 0.0,
    "floor_tilt_max_boost": 2.0,
}


def _overlay_challenger_sha(overlay: dict) -> str:
    """Stable per-overlay pseudo-sha so ON CONFLICT dedup is per-config,
    not per-slate. The prefix marks the row as a knob shadow so the
    rotation-gate CLI can tell it apart from model shadows."""
    canonical = _json.dumps(overlay, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    return f"{_KNOB_SHADOW_PREFIX}{digest}"


def _apply_knob_overlay(
    pred: dict,
    boost: float,
    features: dict,
    overlay: dict,
) -> float:
    """Return the challenger stage-1 rank score for a single pool player.

    Mirrors the head-served path in src/wnba_oracle/scheduler/job2.py:
        pred_real_score = p50 * starter_mult * minutes_lift * floor_tilt
        rank_pred       = pred_real_score, unless boost >= threshold and
                          boost_tail_lift is on -- then p50 is multiplied
                          by lift_factor first.

    ``pred`` is the head quantile dict ({p10, p50, p90}). Only the stage-1
    filter portion is reproduced here -- gs_mult and prop_mult are neutral
    in the overlay path (they still apply upstream identically for
    incumbent and challenger, so they cancel in the RBO/NDCG ordering).
    """
    from wnba_oracle.scheduler.job2_scoring import (
        _floor_tilt_multiplier,
        _starter_minutes_lift,
    )

    p50 = float(pred.get("p50") or 0.0)
    p10 = float(pred.get("p10") or 0.0)
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
    starter_mult *= _starter_minutes_lift(
        features,
        enabled=bool(
            overlay.get(
                "starter_minutes_lift_enabled", _KNOB_DEFAULTS["starter_minutes_lift_enabled"]
            )
        ),
        norm=float(overlay.get("starter_minutes_norm", _KNOB_DEFAULTS["starter_minutes_norm"])),
        weight=float(
            overlay.get(
                "starter_minutes_lift_weight", _KNOB_DEFAULTS["starter_minutes_lift_weight"]
            )
        ),
        cap=float(
            overlay.get("starter_minutes_lift_cap", _KNOB_DEFAULTS["starter_minutes_lift_cap"])
        ),
    )
    floor_mult = _floor_tilt_multiplier(
        p10,
        p50,
        boost,
        weight=float(overlay.get("floor_tilt_weight", _KNOB_DEFAULTS["floor_tilt_weight"])),
        max_boost=float(
            overlay.get("floor_tilt_max_boost", _KNOB_DEFAULTS["floor_tilt_max_boost"])
        ),
    )
    center = p50 * lift_factor if (lift_on and boost >= lift_thresh) else p50
    return max(0.5, center * starter_mult * floor_mult)


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
        rank = _apply_knob_overlay(pred, boost, features, overlay)
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
        "starter_minutes_lift_enabled": bool(
            getattr(settings, "starter_minutes_lift_enabled", False)
        ),
        "starter_minutes_norm": float(getattr(settings, "starter_minutes_norm", 25.0)),
        "starter_minutes_lift_weight": float(getattr(settings, "starter_minutes_lift_weight", 0.6)),
        "starter_minutes_lift_cap": float(getattr(settings, "starter_minutes_lift_cap", 1.3)),
        "floor_tilt_weight": float(getattr(settings, "picker_floor_tilt_weight", 0.0)),
        "floor_tilt_max_boost": float(getattr(settings, "picker_floor_tilt_max_boost", 2.0)),
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
    # Reuse the model-shadow SQL, but stamp the overlay onto the payload so
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
