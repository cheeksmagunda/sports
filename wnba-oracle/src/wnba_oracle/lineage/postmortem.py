"""Pure composition layer for the unified post-slate dossier (#35 phase 3).

Everything here is a deterministic function of records that were already
persisted: the lineage audit built by :mod:`wnba_oracle.lineage.audit`
(``frozen_lineups``, the immutable ``freeze_audit_snapshots`` payload,
``ScoringProvenance`` inside ``lineup.model_provenance``, ``slate_labels``,
``contest_leaderboards``, ``contest_placements``, ``canonical_player_identities``)
plus ``wnba_game_logs`` rows loaded through the canonical identity map.

Nothing in this module re-runs prediction, optimization, or scoring from
current code. When a record needed to answer a question was never persisted,
the section says so with an explicit ``status`` and ``reason`` instead of
inferring a value.

Section status vocabulary (closed set, see ``SECTION_STATUSES``):

- ``available``: every record the section needs is present and exact.
- ``partial``: some records are present; ``reason`` names what is missing.
- ``not_captured``: the record was never persisted for this freeze (for
  example, freezes older than the phase 2 immutable snapshot).
- ``unavailable``: the record should exist but could not be read.
- ``pending``: the slate has not settled yet, so realized data cannot exist.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import text

DOSSIER_SCHEMA_VERSION = 1

SECTION_STATUSES = ("available", "partial", "not_captured", "unavailable", "pending")

# Per-source observation counters written by
# ``assurance.source_quality._source_counts`` into ``source_assurance``.
SOURCE_OBSERVATION_KEYS: dict[str, tuple[str, ...]] = {
    "realsports": ("core_rows",),
    "rotowire": ("starter_rows", "confirmed_rows"),
    "the_odds_api": ("vegas_rows", "prop_rows"),
    "wnba_stats": ("minutes_rows", "head_feature_rows"),
}

GAME_LOG_Q = text(
    """
    SELECT game_date, player_id, player_name, team, opponent, game_id,
           min, pts, reb, ast, stl, blk, tov, fgm, fga, fg3m, ftm, fta, ingested_at
    FROM wnba_game_logs
    WHERE game_date = :game_date
      AND player_id = ANY(:player_ids)
    ORDER BY player_id
    """
)

_BOX_SCORE_FIELDS = (
    "min",
    "pts",
    "reb",
    "ast",
    "stl",
    "blk",
    "tov",
    "fgm",
    "fga",
    "fg3m",
    "ftm",
    "fta",
)

_COMPARISON_NON_SELECTED_LIMIT = 15


def _float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: object) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _pid(value: object) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    try:
        return str(int(text_value))
    except ValueError:
        pass
    try:
        return str(int(float(text_value)))
    except (TypeError, ValueError, OverflowError):
        return text_value


normalize_pid = _pid


# ---------------------------------------------------------------------------
# 1. Source availability
# ---------------------------------------------------------------------------


def source_status(source_assurance: Mapping[str, Any], source: str) -> dict[str, Any]:
    """Per-source availability derived only from recorded observation counts.

    ``assessment_status`` is slate-wide, so it is reported alongside but never
    copied onto an individual source as that source's own status.
    """

    slate_status = source_assurance.get("assessment_status")
    error = source_assurance.get("error")
    if isinstance(error, Mapping):
        return {
            "status": "unavailable",
            "reason": f"assurance_failed:{error.get('type') or 'unknown'}",
            "slate_assessment_status": slate_status,
            "evidence": None,
        }
    observations = source_assurance.get("observations")
    if not isinstance(observations, Mapping):
        return {
            "status": "not_captured",
            "reason": "source_assurance_observations_not_persisted_for_freeze",
            "slate_assessment_status": slate_status,
            "evidence": None,
        }
    evidence = observations.get(source)
    if not isinstance(evidence, Mapping):
        return {
            "status": "not_captured",
            "reason": f"source_assurance.observations.{source}_absent",
            "slate_assessment_status": slate_status,
            "evidence": None,
        }
    capture = _mapping(source_assurance.get("capture"))
    total_rows = capture.get("rows")
    counts = {key: evidence.get(key) for key in SOURCE_OBSERVATION_KEYS.get(source, ())}
    observed = [value for value in counts.values() if isinstance(value, int) and value > 0]
    if not counts or not observed:
        status = "unavailable"
        reason = "zero_rows_observed_at_capture"
    elif isinstance(total_rows, int) and all(
        isinstance(value, int) and value >= total_rows for value in counts.values()
    ):
        status = "available"
        reason = None
    else:
        status = "partial"
        reason = "observed_on_subset_of_pool_rows"
    return {
        "status": status,
        "reason": reason,
        "slate_assessment_status": slate_status,
        "pool_rows": total_rows,
        "evidence": dict(evidence),
        "captured_window": capture or None,
    }


# ---------------------------------------------------------------------------
# 11. Realized box scores via the canonical identity map
# ---------------------------------------------------------------------------


def identity_map(identity_rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in identity_rows:
        pid = _pid(row.get("real_sports_player_id"))
        wnba_id = row.get("wnba_player_id")
        if pid is None or wnba_id is None or isinstance(wnba_id, bool):
            continue
        try:
            out[pid] = int(wnba_id)
        except (TypeError, ValueError):
            continue
    return out


def load_game_logs(
    engine: Any, slate_date: str, wnba_player_ids: Sequence[int]
) -> tuple[list[dict[str, Any]], str | None]:
    """Read box-score rows for mapped players. Returns ``(rows, error_type)``."""

    if not wnba_player_ids:
        return [], None
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                GAME_LOG_Q,
                {"game_date": slate_date, "player_ids": sorted(set(wnba_player_ids))},
            ).fetchall()
    except Exception as exc:
        return [], type(exc).__name__
    return [dict(row._mapping) for row in rows], None


def compose_box_scores(
    *,
    slate_date: str,
    selected_ids: Sequence[str],
    identity_rows: Sequence[Mapping[str, Any]],
    game_log_rows: Sequence[Mapping[str, Any]],
    load_error: str | None = None,
) -> dict[str, Any]:
    """WNBA box scores for the committed five, joined only by the identity map.

    AGENTS.md forbids joining the gamelog and label corpora by name; a
    selected player without a ``canonical_player_identities`` row is reported
    as ``identity_unresolved`` rather than matched heuristically.
    """

    mapping = identity_map(identity_rows)
    by_wnba_id: dict[int, Mapping[str, Any]] = {}
    for row in game_log_rows:
        try:
            by_wnba_id[int(row["player_id"])] = row
        except (KeyError, TypeError, ValueError):
            continue
    players: list[dict[str, Any]] = []
    for pid in selected_ids:
        wnba_id = mapping.get(pid)
        if wnba_id is None:
            players.append(
                {
                    "real_sports_player_id": pid,
                    "identity_status": "identity_unresolved",
                    "box_score_status": "not_joinable",
                    "box_score": None,
                }
            )
            continue
        game_row = by_wnba_id.get(wnba_id)
        if game_row is None:
            players.append(
                {
                    "real_sports_player_id": pid,
                    "wnba_player_id": wnba_id,
                    "identity_status": "resolved",
                    "box_score_status": "unavailable" if load_error else "no_game_log_row",
                    "box_score": None,
                }
            )
            continue
        ingested_at = game_row.get("ingested_at")
        players.append(
            {
                "real_sports_player_id": pid,
                "wnba_player_id": wnba_id,
                "identity_status": "resolved",
                "box_score_status": "available",
                "box_score": {
                    "player_name": game_row.get("player_name"),
                    "team": game_row.get("team"),
                    "opponent": game_row.get("opponent"),
                    "game_id": game_row.get("game_id"),
                    **{field: _float(game_row.get(field)) for field in _BOX_SCORE_FIELDS},
                    "ingested_at": (
                        ingested_at.isoformat()
                        if isinstance(ingested_at, (dt.datetime, dt.date))
                        else ingested_at
                    ),
                },
            }
        )
    available = sum(1 for player in players if player["box_score_status"] == "available")
    if not players:
        status, reason = "unavailable", "no_committed_players"
    elif load_error:
        status, reason = "unavailable", f"game_log_read_failed:{load_error}"
    elif available == len(players):
        status, reason = "available", None
    elif available:
        status, reason = "partial", "some_committed_players_lack_identity_or_game_log"
    elif all(player["identity_status"] == "identity_unresolved" for player in players):
        status, reason = "unavailable", "no_committed_player_has_canonical_identity"
    else:
        status, reason = "pending", "no_game_log_rows_for_slate_date_yet"
    return {
        "status": status,
        "reason": reason,
        "join_basis": (
            "wnba_game_logs.game_date = slate_date AND wnba_game_logs.player_id = "
            "canonical_player_identities.wnba_player_id"
        ),
        "slate_date": slate_date,
        "players": players,
    }


# ---------------------------------------------------------------------------
# 12. Comparison / explanation
# ---------------------------------------------------------------------------


def _realized_by_pid(result_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in result_rows:
        pid = _pid(row.get("platform_player_id"))
        if pid is None:
            continue
        score = _float(row.get("real_score"))
        current = best.get(pid)
        if current is None or (
            score is not None and (current["real_score"] is None or score > current["real_score"])
        ):
            best[pid] = {
                "real_score": score,
                "card_boost": _float(row.get("card_boost")),
                "drafts": row.get("drafts"),
                "display_name": row.get("display_name"),
                "team": row.get("team_key"),
            }
    return best


def _sampling_specs_by_pid(model_provenance: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    optimizer_inputs = _mapping(model_provenance.get("optimizer_inputs"))
    out: dict[str, dict[str, Any]] = {}
    for spec in _list(optimizer_inputs.get("sampling_specs")):
        if not isinstance(spec, Mapping):
            continue
        pid = _pid(spec.get("player_id"))
        if pid is not None:
            out[pid] = dict(spec)
    return out


def _findings(
    *,
    in_decision_inputs: bool | None,
    prediction_path: Mapping[str, Any],
    serve_contract: Mapping[str, Any],
    identity_resolution: Mapping[str, Any],
) -> list[str]:
    """Closed-vocabulary evidence flags. Each one is read off a persisted field."""

    flags: list[str] = []
    if in_decision_inputs is False:
        flags.append("absent_from_decision_inputs")
    tier = prediction_path.get("tier")
    if tier and tier != "trained_heads":
        flags.append(f"fallback_tier:{tier}")
    if _list(serve_contract.get("defaulted_feature_columns")):
        flags.append("head_features_zero_filled")
    availability = _float(prediction_path.get("availability_probability"))
    if availability is not None and availability < 0.5:
        flags.append("availability_hurdle_below_0.5")
    if prediction_path.get("game_script_minutes_redistribution"):
        flags.append("game_script_minutes_redistributed")
    if identity_resolution and identity_resolution.get("status") not in (None, "available"):
        flags.append("identity_unresolved_at_freeze")
    return flags


def compose_comparison(
    *,
    lineup_payload: Mapping[str, Any],
    model_provenance: Mapping[str, Any],
    snapshot_players: Sequence[Mapping[str, Any]] | None,
    result_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Join persisted predictions to realized values; never recompute either.

    ``explanation_basis`` states which record the predicted side comes from:

    - ``snapshot_exact``: per-player prediction path from the immutable
      phase 2 freeze snapshot (``final_optimizer_score``).
    - ``optimizer_inputs``: ``ScoringProvenance.optimizer_inputs`` sampling
      specs; ``optimizer_median = exp(mu)`` of the persisted log-normal spec,
      with no tier or adjustment detail.
    - ``selected_players_only``: only the frozen five's
      ``pred_real_score_p50`` from ``frozen_lineups.lineup.per_player``.
    - ``unavailable``: no persisted prediction for this freeze.
    """

    selected_ids = [
        pid for pid in (_pid(value) for value in _list(lineup_payload.get("player_ids"))) if pid
    ]
    per_player = {
        _pid(item.get("player_id")): item
        for item in _list(lineup_payload.get("per_player"))
        if isinstance(item, Mapping) and _pid(item.get("player_id"))
    }
    snapshot_by_pid = {
        _pid(player.get("real_sports_player_id")): player
        for player in (snapshot_players or [])
        if isinstance(player, Mapping) and _pid(player.get("real_sports_player_id"))
    }
    specs = _sampling_specs_by_pid(model_provenance)
    realized = _realized_by_pid(result_rows)

    if snapshot_by_pid:
        basis = "snapshot_exact"
    elif specs:
        basis = "optimizer_inputs"
    elif per_player:
        basis = "selected_players_only"
    else:
        basis = "unavailable"

    decision_universe = set(snapshot_by_pid) | set(specs)

    def row_for(pid: str) -> dict[str, Any]:
        snapshot = _mapping(snapshot_by_pid.get(pid))
        prediction_path = _mapping(snapshot.get("prediction_path"))
        serve_contract = _mapping(snapshot.get("serve_contract"))
        identity = _mapping(snapshot.get("identity_resolution"))
        spec = specs.get(pid)
        frozen = _mapping(per_player.get(pid))
        mu = _float(spec.get("mu")) if spec else None
        realized_row = realized.get(pid)
        predicted_final = _float(prediction_path.get("final_optimizer_score"))
        predicted_p50 = _float(frozen.get("pred_real_score_p50")) if frozen else None
        optimizer_median = math.exp(mu) if mu is not None and mu < 50 else None
        predicted = predicted_final
        predicted_basis = "snapshot.final_optimizer_score" if predicted is not None else None
        if predicted is None and predicted_p50 is not None:
            predicted, predicted_basis = predicted_p50, "frozen_lineup.pred_real_score_p50"
        if predicted is None and optimizer_median is not None:
            predicted, predicted_basis = optimizer_median, "exp(sampling_spec.mu)"
        realized_score = realized_row.get("real_score") if realized_row else None
        in_inputs = (pid in decision_universe) if decision_universe else None
        return {
            "real_sports_player_id": pid,
            "display_name": (
                frozen.get("display_name")
                or snapshot.get("display_name")
                or (realized_row or {}).get("display_name")
            ),
            "selected": pid in selected_ids,
            "slot": selected_ids.index(pid) + 1 if pid in selected_ids else None,
            "in_decision_inputs": in_inputs,
            "prediction_tier": prediction_path.get("tier") or None,
            "predicted": predicted,
            "predicted_basis": predicted_basis,
            "optimizer_median": optimizer_median,
            "p_active": _float(spec.get("p_active")) if spec else None,
            "realized_real_score": realized_score,
            "realized_status": (
                "available"
                if realized_score is not None
                else ("pending" if not result_rows else "no_label_row")
            ),
            "realized_minus_predicted": (
                realized_score - predicted
                if realized_score is not None and predicted is not None
                else None
            ),
            "findings": _findings(
                in_decision_inputs=in_inputs,
                prediction_path=prediction_path,
                serve_contract=serve_contract,
                identity_resolution=identity,
            ),
        }

    selected_rows = [row_for(pid) for pid in selected_ids]
    non_selected_realized = sorted(
        (pid for pid in realized if pid not in selected_ids),
        key=lambda pid: (
            realized[pid]["real_score"] is None,
            -(realized[pid]["real_score"] or 0.0),
            pid,
        ),
    )[:_COMPARISON_NON_SELECTED_LIMIT]
    alternatives = [row_for(pid) for pid in non_selected_realized]

    if basis == "unavailable":
        status, reason = "unavailable", "no_persisted_prediction_for_freeze"
    elif not result_rows:
        status, reason = "pending", "realized_results_pending"
    elif basis == "snapshot_exact":
        status, reason = "available", None
    else:
        status = "partial"
        reason = (
            "prediction_tier_and_adjustments_not_captured_pre_phase2"
            if basis == "optimizer_inputs"
            else "only_selected_player_predictions_persisted"
        )
    return {
        "status": status,
        "reason": reason,
        "explanation_basis": basis,
        "selected": selected_rows,
        "top_realized_not_selected": alternatives,
        "top_realized_not_selected_limit": _COMPARISON_NON_SELECTED_LIMIT,
        "findings_vocabulary": [
            "absent_from_decision_inputs",
            "fallback_tier:<tier>",
            "head_features_zero_filled",
            "availability_hurdle_below_0.5",
            "game_script_minutes_redistributed",
            "identity_unresolved_at_freeze",
        ],
        "note": (
            "Findings are evidence flags read from persisted records; they do not "
            "assert causation. realized_minus_predicted compares the persisted "
            "prediction named by predicted_basis to slate_labels.real_score."
        ),
    }


# ---------------------------------------------------------------------------
# Section index over the 12 issue points and top-level settlement status
# ---------------------------------------------------------------------------


def _entry(point: int, name: str, keys: Sequence[str], status: str, reason: str | None) -> dict:
    return {
        "point": point,
        "name": name,
        "keys": list(keys),
        "status": status,
        "reason": reason,
    }


def _rollup(statuses: Sequence[str]) -> str:
    if not statuses:
        return "unavailable"
    if all(status == "available" for status in statuses):
        return "available"
    if all(status == "pending" for status in statuses):
        return "pending"
    if any(status in ("available", "partial") for status in statuses):
        return "partial"
    return statuses[0]


def settlement_status(payload: Mapping[str, Any]) -> tuple[str, str | None]:
    realized = _mapping(payload.get("realized_player_results"))
    contest = _mapping(payload.get("contest_results"))
    outcome = _mapping(payload.get("our_outcome"))
    if realized.get("status") != "available":
        return "pending", "slate_labels_not_ingested_yet"
    missing = []
    if _mapping(contest.get("leaderboard_status")).get("status") != "available":
        missing.append("contest_leaderboards")
    if outcome.get("status") != "available":
        missing.append("contest_placements")
    if missing:
        return "partial", "missing:" + ",".join(missing)
    return "finalized", None


def section_index(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    sources = _mapping(payload.get("sources"))
    input_snapshot = _mapping(payload.get("input_snapshot"))
    lineage = _mapping(payload.get("feature_and_signal_lineage"))
    artifact = _mapping(lineage.get("artifact_contract"))
    prediction = _mapping(payload.get("prediction_paths"))
    optimizer = _mapping(payload.get("optimizer"))
    frozen = _mapping(payload.get("frozen_lineup"))
    realized = _mapping(payload.get("realized_player_results"))
    contest = _mapping(payload.get("contest_results"))
    outcome = _mapping(payload.get("our_outcome"))
    box = _mapping(payload.get("box_scores"))
    comparison = _mapping(payload.get("comparison"))
    identity = _mapping(sources.get("identity_mapping"))

    source_statuses = [
        str(_mapping(sources.get(name)).get("status") or "not_captured")
        for name in (*SOURCE_OBSERVATION_KEYS, "model_artifact", "payout_archive")
    ]
    source_rollup = _rollup(source_statuses)

    snap_status = str(input_snapshot.get("status") or "")
    captured: tuple[str, str | None]
    feature: tuple[str, str | None]
    pred: tuple[str, str | None]
    if snap_status in ("bound_snapshot_available", "current_rows_match_freeze_exactly"):
        captured = ("available", None)
    elif snap_status == "current_rows_match_freeze_canonically_only":
        captured = ("partial", "row_order_differs_from_freeze")
    elif snap_status == "current_rows_do_not_match_freeze":
        captured = ("not_captured", "historical_job1_state_mutated_since_freeze")
    else:
        captured = ("unavailable", input_snapshot.get("reason") or "input_snapshot_missing")

    identity_status = str(identity.get("status") or "unavailable")
    identity_reason = identity.get("reason")
    coverage = _mapping(identity.get("coverage"))
    if identity_status == "available" and coverage.get("unresolved"):
        identity_status, identity_reason = "partial", "some_pool_players_unresolved"

    if captured[0] == "available":
        feature = ("available", None)
    else:
        feature = ("partial", "feature values reflect current job1_enrichment, not freeze time")

    artifact_status = "available" if artifact.get("status") == "available" else "unavailable"
    artifact_reason = None if artifact_status == "available" else artifact.get("reason")

    if prediction.get("status") == "captured_in_immutable_snapshot":
        pred = ("available", None)
    else:
        pred = ("not_captured", prediction.get("reason") or "prediction_paths_not_persisted")

    policy_ok = bool(optimizer.get("model_policy_sha256")) and bool(
        _mapping(optimizer.get("model_provenance")).get("model_policy")
    )
    policy = ("available", None) if policy_ok else ("not_captured", "model_policy_not_persisted")
    opt_ok = bool(optimizer.get("optimizer_input_hash")) and bool(
        _mapping(optimizer.get("model_provenance")).get("optimizer_inputs")
    )
    opt = (
        ("available", None)
        if opt_ok
        else (str(optimizer.get("status") or "not_captured"), optimizer.get("reason"))
    )
    if opt[0] == "available" and not optimizer.get("optimizer_input_hash"):
        opt = ("partial", "optimizer_input_hash_missing")

    freeze = (
        ("available", None)
        if frozen.get("audit_snapshot_sha256")
        else ("partial", "freeze_predates_phase2_audit_snapshot")
    )

    realized_statuses = [
        str(realized.get("status") or "unavailable"),
        str(_mapping(contest.get("leaderboard_status")).get("status") or "unavailable"),
        str(outcome.get("status") or "unavailable"),
        str(box.get("status") or "unavailable"),
    ]
    realized_rollup = _rollup(realized_statuses)
    if realized.get("status") == "pending":
        realized_rollup = "pending"

    return [
        _entry(
            1,
            "source_availability",
            ["sources"],
            source_rollup,
            None if source_rollup == "available" else "see per-source status",
        ),
        _entry(2, "captured_state", ["input_snapshot"], *captured),
        _entry(
            3,
            "identity_resolution",
            ["sources.identity_mapping", "prediction_paths.rows[].identity_resolution"],
            identity_status,
            identity_reason,
        ),
        _entry(4, "feature_materialization", ["feature_and_signal_lineage.matrix"], *feature),
        _entry(
            5,
            "training_contract",
            ["feature_and_signal_lineage.artifact_contract"],
            artifact_status,
            artifact_reason,
        ),
        _entry(6, "serve_contract", ["prediction_paths.rows[].serve_contract"], *pred),
        _entry(7, "prediction_path", ["prediction_paths.rows[].prediction_path"], *pred),
        _entry(
            8,
            "policy_configuration",
            ["optimizer.model_provenance.model_policy", "optimizer.serving_knobs"],
            *policy,
        ),
        _entry(9, "optimizer_state", ["optimizer"], *opt),
        _entry(10, "freeze_audit_state", ["frozen_lineup"], *freeze),
        _entry(
            11,
            "realized_outcome",
            ["realized_player_results", "contest_results", "our_outcome", "box_scores"],
            realized_rollup,
            None if realized_rollup == "available" else "see per-section status",
        ),
        _entry(
            12,
            "comparison",
            ["comparison"],
            str(comparison.get("status") or "unavailable"),
            comparison.get("reason"),
        ),
    ]


def finalize_dossier(
    payload: dict[str, Any],
    *,
    snapshot_players: Sequence[Mapping[str, Any]] | None,
    result_rows: Sequence[Mapping[str, Any]],
    game_log_rows: Sequence[Mapping[str, Any]],
    game_log_error: str | None,
    identity_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Add box scores, comparison, section index, and settlement status.

    ``identity_rows`` defaults to ``sources.identity_mapping.rows`` (the pool
    lookup); callers pass a superset when committed players were resolved
    separately because the slate's ``job1_enrichment`` rows no longer exist.
    """

    frozen = _mapping(payload.get("frozen_lineup"))
    lineup_payload = _mapping(frozen.get("lineup"))
    model_provenance = _mapping(lineup_payload.get("model_provenance"))
    if identity_rows is None:
        identity_rows = _list(
            _mapping(_mapping(payload.get("sources")).get("identity_mapping")).get("rows")
        )
    selected_ids = [
        pid for pid in (_pid(value) for value in _list(lineup_payload.get("player_ids"))) if pid
    ]
    payload["box_scores"] = compose_box_scores(
        slate_date=str(payload.get("slate_date") or ""),
        selected_ids=selected_ids,
        identity_rows=identity_rows,
        game_log_rows=game_log_rows,
        load_error=game_log_error,
    )
    payload["comparison"] = compose_comparison(
        lineup_payload=lineup_payload,
        model_provenance=model_provenance,
        snapshot_players=snapshot_players,
        result_rows=result_rows,
    )
    status, reason = settlement_status(payload)
    payload["dossier_schema_version"] = DOSSIER_SCHEMA_VERSION
    payload["status"] = status
    payload["status_reason"] = reason
    payload["sections"] = section_index(payload)
    return payload
