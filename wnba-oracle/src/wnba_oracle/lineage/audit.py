"""Read-only slate lineage reconstruction and expanded post-slate dossier."""

from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from oracle_core import (
    Achievability,
    DataQualityAndCensoring,
    EntryKind,
    FeasibilityConstraint,
    FeasibleActionFamily,
    KnowledgeState,
    LearningSummary,
    ProvenanceStatus,
    RealizedOutcomes,
    SlateDossier,
    SlateEntry,
    SlateIdentity,
    SlotSelection,
    build_gap_analysis,
)
from sqlalchemy import text

from wnba_oracle.api.results import _top_value
from wnba_oracle.db.engine import get_api_engine
from wnba_oracle.dossier import DEFAULT_SLOTS, build_dossier
from wnba_oracle.lineage.freeze_snapshot import FREEZE_AUDIT_SNAPSHOT_SELECT
from wnba_oracle.lineage.postmortem import (
    finalize_dossier,
    identity_map,
    load_game_logs,
    normalize_pid,
    source_status,
)
from wnba_oracle.modeling.provenance import (
    canonical_enrichment_payload,
    enrichment_sequence_payload,
)
from wnba_oracle.scheduler.job2_model import REPO_ROOT, _load_model_artifact

_FREEZE_Q = text(
    """
    SELECT id, slate_date, model_sha, payout_regime, frozen_at, lineup,
           entry_recommendation, expected_payout, metadata_json,
           freeze_seq, frozen_via, operation_key, audit_snapshot_sha256
    FROM frozen_lineups
    WHERE slate_date = :slate_date
      AND (:model_sha = '' OR model_sha = :model_sha)
    ORDER BY frozen_at DESC, id DESC
    LIMIT 1
    """
)

_ALL_FREEZES_Q = text(
    """
    SELECT id, model_sha, frozen_at, freeze_seq, frozen_via, operation_key, audit_snapshot_sha256
    FROM frozen_lineups
    WHERE slate_date = :slate_date
    ORDER BY frozen_at ASC, id ASC
    """
)

_ENRICHMENT_Q = text(
    """
    SELECT real_sports_player_id, name, team, opponent, position,
           card_boost, features_json, captured_at
    FROM job1_enrichment
    WHERE slate_date = :slate_date
    ORDER BY real_sports_player_id
    """
)

_RESULTS_Q = text(
    """
    SELECT contest_id, slate_date, section, platform_player_id, display_name,
           team_key, card_boost, drafts, real_score, ingested_at
    FROM slate_labels
    WHERE slate_date = :slate_date
    ORDER BY section, real_score DESC NULLS LAST, platform_player_id
    """
)

_LEADERBOARD_Q = text(
    """
    SELECT contest_id, entry_id, rank, paged_rank, user_id, score,
           lineup, num_brawlers, ingested_at
    FROM contest_leaderboards
    WHERE slate_date = :slate_date
    ORDER BY rank ASC, entry_id ASC
    """
)

_PLACEMENT_Q = text(
    """
    SELECT slate_date, contest_id, recorded_at, source, entry_rank, entry_count,
           entry_score, payout_received_cents, entry_fee_cents, finish_percentile,
           cashed, top_10pct, top_1pct, roi, freeze_model_sha, expected_payout,
           lineup_score_p10, lineup_score_p50, lineup_score_p90, payout_curve_json,
           freeze_config_json, predicted_ownership_json, actual_ownership_json, metadata_json
    FROM contest_placements
    WHERE slate_date = :slate_date
    ORDER BY recorded_at DESC
    LIMIT 1
    """
)

_SLATE_META_Q = text(
    """
    SELECT slate_date, first_tip_utc, contest_lock_utc, source, payload_json, updated_at
    FROM slate_meta
    WHERE slate_date = :slate_date
    """
)

_CANONICAL_IDENTITY_Q = text(
    """
    SELECT real_sports_player_id, wnba_player_id, provenance, provider_nba_id,
           real_sports_display_name, real_sports_team, wnba_full_name,
           first_seen_at, last_seen_at
    FROM canonical_player_identities
    WHERE real_sports_player_id = ANY(:real_sports_ids)
    ORDER BY real_sports_player_id
    """
)


def _utc_iso(value: object) -> str | None:
    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC).isoformat()


def _float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cents_to_dollars(value: object) -> float | None:
    cents = _float(value)
    if cents is None:
        return None
    return cents / 100.0


def _int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _mapping(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _sequence(value: object) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _load_artifact_contract(model_sha: str) -> dict[str, Any]:
    art = _load_model_artifact(model_sha)
    if art is not None:
        return {
            "status": "available",
            "artifact_sha256": model_sha,
            "artifact_source": "pickle",
            "feature_module_sha": art.feature_module_sha,
            "cohorts_trained": list(getattr(art, "cohorts_trained", ())),
            "heads_trained": sorted(f"{name}:{cohort}" for (name, cohort) in art.heads),
            "feature_subset_per_head": {
                f"{name}:{cohort}": list(columns)
                for (name, cohort), columns in sorted(art.feature_subset_per_head.items())
            },
        }
    manifest_dir = REPO_ROOT / "models"
    for manifest in sorted(manifest_dir.glob("picker_*.manifest.json")):
        try:
            payload = json.loads(manifest.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if str(payload.get("artifact_sha256", "")).strip().lower() != model_sha.lower():
            continue
        return {
            "status": "available",
            "artifact_sha256": model_sha,
            "artifact_source": "manifest",
            "feature_module_sha": payload.get("feature_module_sha"),
            "cohorts_trained": list(payload.get("cohorts_trained", [])),
            "heads_trained": list(payload.get("heads_trained", [])),
            "feature_subset_per_head": dict(payload.get("cohort_feature_contract", {})),
        }
    return {
        "status": "unavailable",
        "artifact_sha256": model_sha,
        "reason": "artifact_not_present_in_workspace",
    }


def _prediction_path_rows(snapshot: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not snapshot:
        return []
    players = snapshot.get("players")
    if not isinstance(players, list):
        return []
    rows: list[dict[str, Any]] = []
    for player in players:
        if not isinstance(player, Mapping):
            continue
        rows.append(
            {
                "real_sports_player_id": str(player.get("real_sports_player_id") or ""),
                "display_name": player.get("display_name"),
                "prediction_path": player.get("prediction_path"),
                "serve_contract": player.get("serve_contract"),
                "identity_resolution": player.get("identity_resolution"),
            }
        )
    return rows


def _artifact_feature_matrix(
    artifact_contract: Mapping[str, Any],
    *,
    enrichment_rows: Sequence[Mapping[str, Any]],
    prediction_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if artifact_contract.get("status") != "available":
        return [
            {
                "signal": "artifact_feature_subset_per_head",
                "status": "unavailable",
                "reason": artifact_contract.get("reason", "artifact_unavailable"),
            }
        ]
    prediction_by_pid = {
        str(row.get("real_sports_player_id") or ""): row
        for row in prediction_rows
        if row.get("real_sports_player_id")
    }
    subset = artifact_contract.get("feature_subset_per_head")
    if not isinstance(subset, Mapping):
        subset = {}
    rows: list[dict[str, Any]] = []
    for head_key, columns_obj in sorted(subset.items()):
        columns = [str(column) for column in columns_obj] if isinstance(columns_obj, list) else []
        counts: Counter[str] = Counter()
        for enrichment in enrichment_rows:
            pid = str(enrichment.get("real_sports_player_id") or "")
            prediction = prediction_by_pid.get(pid, {})
            prediction_path = (
                prediction.get("prediction_path") if isinstance(prediction, Mapping) else {}
            )
            if not isinstance(prediction_path, Mapping):
                prediction_path = {}
            tier = str(prediction_path.get("tier") or "")
            if head_key in {"minutes:F", "real_score_per_min:F"} and tier == "trained_heads":
                serve_contract = (
                    prediction.get("serve_contract") if isinstance(prediction, Mapping) else {}
                )
                serve_contract = serve_contract if isinstance(serve_contract, Mapping) else {}
                defaulted = set(serve_contract.get("defaulted_feature_columns", []))
                provided = set(serve_contract.get("provided_feature_columns", []))
                counts["trained_head_rows"] += 1
                counts["provided_values"] += len(provided)
                counts["defaulted_values"] += len(defaulted)
            elif head_key in {"minutes:F", "real_score_per_min:F"}:
                counts["non_consumed_rows"] += 1
        rows.append(
            {
                "signal": head_key,
                "source": "trained_artifact",
                "capture_code_path": "train.pipeline.train_picker",
                "persisted_location": "picker_*.pkl or picker_*.manifest.json",
                "timestamp_freshness_semantics": "artifact bytes are immutable once written",
                "identity_dependency": "none at artifact contract level; serving rows map by real_sports_player_id",
                "training_availability": "artifact_exact",
                "exact_artifact_consumption_status": {
                    "feature_columns": columns,
                    **counts,
                },
                "serve_time_availability": {
                    "rows_with_current_snapshot": len(prediction_rows),
                },
                "default_fallback_behavior": "missing head feature columns zero-fill in _predict_heads_for_pool",
                "downstream_transformation_or_policy_use": [
                    "artifact.predict_real_score",
                    "prediction tier routing",
                ],
                "optimizer_use": "indirect via pred_real_score and quantiles",
                "freeze_persistence_status": "phase_2 immutable snapshot when audit_snapshot_sha256 exists",
                "realized_outcome_availability": "joined later through slate_labels / placements",
            }
        )
    return rows


def _static_signal_matrix(
    *,
    enrichment_rows: Sequence[Mapping[str, Any]],
    prediction_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    total_rows = len(enrichment_rows)
    trained_rows = sum(
        1
        for row in prediction_rows
        if isinstance(row.get("prediction_path"), Mapping)
        and row["prediction_path"].get("tier") == "trained_heads"
    )
    return [
        {
            "signal": "job1_enrichment.card_boost",
            "source": "Real Sports pool",
            "capture_code_path": "scheduler.job1._build_enrichment_rows",
            "persisted_location": "job1_enrichment.card_boost",
            "timestamp_freshness_semantics": "job1_enrichment.captured_at per player row",
            "identity_dependency": "real_sports_player_id",
            "training_availability": "not_in_artifact_heads",
            "exact_artifact_consumption_status": "fallback tiers only",
            "serve_time_availability": {"present_rows": total_rows, "total_rows": total_rows},
            "default_fallback_behavior": "required numeric field; heuristic paths cast missing values to 0.0",
            "downstream_transformation_or_policy_use": [
                "heuristic prediction",
                "tail-lift policy",
                "field popularity fallback",
            ],
            "optimizer_use": "sampling boost and field specs.card_boost",
            "freeze_persistence_status": "selected players persisted in frozen_lineups.lineup.per_player",
            "realized_outcome_availability": "slate_labels.card_boost",
        },
        {
            "signal": "features_json injury/starter bundle",
            "source": "RotoWire lineups",
            "capture_code_path": "scheduler.job1._build_enrichment_rows",
            "persisted_location": "job1_enrichment.features_json.{injury_status,is_out,is_starter,starter_slot,rotowire_confirmed}",
            "timestamp_freshness_semantics": "shares job1_enrichment.captured_at",
            "identity_dependency": "normalized team + display_name match in job1",
            "training_availability": "not_in_artifact_heads directly",
            "exact_artifact_consumption_status": "starter multipliers and availability hurdle; not consumed by trained heads",
            "serve_time_availability": {"present_rows": total_rows, "total_rows": total_rows},
            "default_fallback_behavior": "missing starter data falls back to neutral multipliers / role interval",
            "downstream_transformation_or_policy_use": [
                "starter_multiplier",
                "starter_minutes_lift",
                "availability_probability",
            ],
            "optimizer_use": "indirect via pred_real_score and minutes intervals",
            "freeze_persistence_status": "not copied verbatim before phase 2; inference only from current enrichment unless snapshot bound",
            "realized_outcome_availability": "none",
        },
        {
            "signal": "features_json vegas + props bundle",
            "source": "The Odds API",
            "capture_code_path": "scheduler.job1._build_enrichment_rows",
            "persisted_location": "job1_enrichment.features_json.{vegas_total,vegas_spread,is_home,prop_*}",
            "timestamp_freshness_semantics": "shares job1_enrichment.captured_at",
            "identity_dependency": "team/opponent mapping from odds slate",
            "training_availability": "head_features incorporate pace/DvP; vegas/props are runtime-only",
            "exact_artifact_consumption_status": f"{trained_rows} trained-head rows this slate plus runtime prop/game-script multipliers",
            "serve_time_availability": {"present_rows": total_rows, "total_rows": total_rows},
            "default_fallback_behavior": "missing vegas -> neutral game_script_multiplier; missing props -> neutral prop multiplier",
            "downstream_transformation_or_policy_use": [
                "game_script_multiplier",
                "prop_signal_multiplier",
                "stack decision context",
            ],
            "optimizer_use": "indirect via pred_real_score and contextual stacking",
            "freeze_persistence_status": "not copied verbatim before phase 2; inference only from current enrichment unless snapshot bound",
            "realized_outcome_availability": "none",
        },
        {
            "signal": "features_json minutes + head_features bundle",
            "source": "stats.wnba.com derived features",
            "capture_code_path": "scheduler.job1._build_enrichment_rows",
            "persisted_location": "job1_enrichment.features_json.{recent_minutes,per_min_rate,minutes_vol,n_min_games,head_features}",
            "timestamp_freshness_semantics": "shares job1_enrichment.captured_at",
            "identity_dependency": "canonical resolver / head_feature lookup",
            "training_availability": "artifact_exact when model file or manifest is present",
            "exact_artifact_consumption_status": "see artifact feature rows below",
            "serve_time_availability": {"present_rows": total_rows, "total_rows": total_rows},
            "default_fallback_behavior": "missing minutes -> fallback tiers; missing head feature keys zero-fill when trained heads run",
            "downstream_transformation_or_policy_use": [
                "minutes tier",
                "trained heads tier",
                "volatility",
            ],
            "optimizer_use": "indirect via pred_real_score, sigma, and projected intervals",
            "freeze_persistence_status": "not copied verbatim before phase 2; exact when audit snapshot exists",
            "realized_outcome_availability": "slate_labels real_score only, not raw box-score features",
        },
    ]


def _current_enrichment_reconstruction(
    enrichment_rows: Sequence[Mapping[str, Any]],
    stored_provenance: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if snapshot is not None:
        return {
            "status": "bound_snapshot_available",
            "audit_snapshot_sha256": snapshot.get("snapshot_sha256"),
            "snapshot_created_at_utc": snapshot.get("created_at_utc"),
            "rows": snapshot.get("payload_json", {}).get("players", []),
            "binding": "exact_freeze_time_snapshot",
        }
    if not enrichment_rows:
        return {
            "status": "unavailable",
            "reason": "job1_enrichment_missing_for_slate",
        }
    current_sequence_sha = None
    current_canonical_sha = None
    try:
        current_sequence_sha = enrichment_sequence_payload(enrichment_rows)
        current_canonical_sha = canonical_enrichment_payload(enrichment_rows)
    except Exception:
        pass
    current_sequence_digest = (
        hashlib.sha256(current_sequence_sha).hexdigest() if current_sequence_sha else None
    )
    current_canonical_digest = (
        hashlib.sha256(current_canonical_sha).hexdigest() if current_canonical_sha else None
    )
    stored_sequence = stored_provenance.get("enrichment_sequence_sha256")
    stored_canonical = stored_provenance.get("enrichment_sha256")
    if current_sequence_digest and current_sequence_digest == stored_sequence:
        status = "current_rows_match_freeze_exactly"
        binding = "exact_from_current_job1_enrichment"
    elif current_canonical_digest and current_canonical_digest == stored_canonical:
        status = "current_rows_match_freeze_canonically_only"
        binding = "same_semantic_rows_different_order"
    else:
        status = "current_rows_do_not_match_freeze"
        binding = "historical_exact_snapshot_not_captured"
    return {
        "status": status,
        "binding": binding,
        "stored_enrichment_sequence_sha256": stored_sequence,
        "stored_enrichment_sha256": stored_canonical,
        "current_enrichment_sequence_sha256": current_sequence_digest,
        "current_enrichment_sha256": current_canonical_digest,
        "rows": [
            {
                "real_sports_player_id": row.get("real_sports_player_id"),
                "name": row.get("name"),
                "team": row.get("team"),
                "opponent": row.get("opponent"),
                "position": row.get("position"),
                "card_boost": _float(row.get("card_boost")),
                "captured_at_utc": _utc_iso(row.get("captured_at")),
                "features_json": row.get("features_json"),
            }
            for row in enrichment_rows
        ],
        "follow_up": (
            None
            if status == "current_rows_match_freeze_exactly"
            else "historical exact freeze-time rows were not bound before issue #35 phase 2"
        ),
    }


def _load_snapshot_payload(conn: Any, snapshot_sha256: str | None) -> dict[str, Any] | None:
    if not snapshot_sha256:
        return None
    row = conn.execute(
        FREEZE_AUDIT_SNAPSHOT_SELECT,
        {"snapshot_sha256": snapshot_sha256},
    ).first()
    if row is None:
        return None
    payload = row._mapping.get("payload_json")
    return {
        "snapshot_sha256": row._mapping.get("snapshot_sha256"),
        "schema_version": row._mapping.get("schema_version"),
        "created_at_utc": _utc_iso(row._mapping.get("created_at")),
        "payload_json": payload if isinstance(payload, Mapping) else _mapping(payload),
    }


def _load_rows(conn: Any, query: Any, params: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(row._mapping) for row in conn.execute(query, params).fetchall()]


def _identity_resolution_rows(
    conn: Any, enrichment_rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    real_sports_ids = [
        str(row.get("real_sports_player_id") or "").strip() for row in enrichment_rows
    ]
    real_sports_ids = [player_id for player_id in real_sports_ids if player_id]
    if not real_sports_ids:
        return []
    try:
        rows = _load_rows(conn, _CANONICAL_IDENTITY_Q, {"real_sports_ids": real_sports_ids})
    except Exception:
        return []
    return [
        {
            "status": "available",
            "real_sports_player_id": str(row["real_sports_player_id"]),
            "wnba_player_id": _int(row.get("wnba_player_id")),
            "provenance": row.get("provenance"),
            "provider_nba_id": _int(row.get("provider_nba_id")),
            "real_sports_display_name": row.get("real_sports_display_name"),
            "real_sports_team": row.get("real_sports_team"),
            "wnba_full_name": row.get("wnba_full_name"),
            "first_seen_at": _utc_iso(row.get("first_seen_at")),
            "last_seen_at": _utc_iso(row.get("last_seen_at")),
        }
        for row in rows
    ]


def _results_sections(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "status": "pending",
            "rows": [],
            "top_value": [],
        }
    out_rows = []
    for row in rows:
        item = dict(row)
        item["ingested_at"] = _utc_iso(row.get("ingested_at"))
        out_rows.append(item)
    return {
        "status": "available",
        "rows": out_rows,
        "top_value": _top_value(out_rows),
    }


def _slots_from_committed_lineup(lineup_payload: Mapping[str, Any]) -> tuple[SlotSelection, ...]:
    per_player = lineup_payload.get("per_player")
    per_player = per_player if isinstance(per_player, list) else []
    player_ids = lineup_payload.get("player_ids")
    player_ids = player_ids if isinstance(player_ids, list) else []
    slots: list[SlotSelection] = []
    for index, player_id in enumerate(player_ids[:5], start=1):
        detail = (
            per_player[index - 1]
            if index - 1 < len(per_player) and isinstance(per_player[index - 1], Mapping)
            else {}
        )
        slots.append(
            SlotSelection(
                position=index,
                slot_id=f"slot_{index}",
                participant_id=str(player_id),
                participant_name=str(detail.get("display_name") or "") or None,
                team_id=str(detail.get("team") or "") or None,
                team_name=str(detail.get("team") or "") or None,
                role_name=str(detail.get("position") or "") or None,
            )
        )
    return tuple(slots)


def _slots_from_leaderboard_row(row: Mapping[str, Any]) -> tuple[SlotSelection, ...]:
    lineup = row.get("lineup")
    entries = _sequence(lineup)
    slots: list[SlotSelection] = []
    for index, player in enumerate(entries[:5], start=1):
        if not isinstance(player, Mapping):
            continue
        slots.append(
            SlotSelection(
                position=index,
                slot_id=f"slot_{index}",
                participant_id=str(
                    player.get("playerId") or player.get("player_id") or f"unknown-{index}"
                ),
                participant_name=str(player.get("displayName") or player.get("display_name") or "")
                or None,
                team_id=str(player.get("team") or "") or None,
                team_name=str(player.get("team") or "") or None,
                role_name=str(player.get("position") or "") or None,
            )
        )
    return tuple(slots)


def _theoretical_best_slots(result_rows: Sequence[Mapping[str, Any]]) -> tuple[SlotSelection, ...]:
    best_by_player: dict[str, dict[str, Any]] = {}
    for row in result_rows:
        if row.get("real_score") is None or row.get("team_key") is None:
            continue
        player_id = str(row.get("platform_player_id") or "")
        if not player_id:
            continue
        current = best_by_player.get(player_id)
        if current is None or float(row.get("real_score") or 0.0) > float(
            current.get("real_score") or 0.0
        ):
            best_by_player[player_id] = dict(row)
    candidate_rows = sorted(
        best_by_player.values(),
        key=lambda row: (
            -(float(row.get("real_score") or 0.0) * (2.0 + float(row.get("card_boost") or 0.0)))
        ),
    )[:26]
    best_rows: list[dict[str, Any]] = []
    best_score = -1.0
    for combo in itertools.combinations(candidate_rows[:26], 5):
        team_counts = Counter(str(row.get("team_key") or "") for row in combo)
        if team_counts and max(team_counts.values()) > 2:
            continue
        ordered = sorted(combo, key=lambda row: float(row.get("real_score") or 0.0), reverse=True)
        score = 0.0
        for multiplier, row in zip(DEFAULT_SLOTS, ordered, strict=True):
            score += float(row.get("real_score") or 0.0) * (
                float(multiplier) + float(row.get("card_boost") or 0.0)
            )
        if score > best_score:
            best_score = score
            best_rows = ordered
    slots: list[SlotSelection] = []
    for index, row in enumerate(best_rows[:5], start=1):
        slots.append(
            SlotSelection(
                position=index,
                slot_id=f"slot_{index}",
                participant_id=str(row.get("platform_player_id") or f"theory-{index}"),
                participant_name=str(row.get("display_name") or "") or None,
                team_id=str(row.get("team_key") or "") or None,
                team_name=str(row.get("team_key") or "") or None,
            )
        )
    return tuple(slots)


def _shared_slate_dossier(
    *,
    slate_date: str,
    freeze_row: Mapping[str, Any],
    legacy_dossier: Any,
    results_rows: Sequence[Mapping[str, Any]],
    leaderboard_rows: Sequence[Mapping[str, Any]],
    placement_row: Mapping[str, Any] | None,
    audit: Mapping[str, Any],
) -> dict[str, Any] | None:
    if legacy_dossier is None:
        return None
    lineup_payload = _mapping(freeze_row.get("lineup"))
    field_entry = leaderboard_rows[0] if leaderboard_rows else None
    if not lineup_payload or field_entry is None:
        return None
    committed_slots = _slots_from_committed_lineup(lineup_payload)
    field_slots = _slots_from_leaderboard_row(field_entry)
    theoretical_slots = _theoretical_best_slots(results_rows)
    if len(committed_slots) != 5 or len(field_slots) != 5 or len(theoretical_slots) != 5:
        return None
    our_rank = _int(placement_row.get("entry_rank")) if placement_row else None
    payout = (
        _cents_to_dollars(placement_row.get("payout_received_cents")) if placement_row else None
    )
    field_size = _int(field_entry.get("num_brawlers")) if field_entry else None
    our_percentile = _float(placement_row.get("finish_percentile")) if placement_row else None
    data_quality = audit.get("data_quality_and_censoring", {})
    provenance = ProvenanceStatus(
        str(data_quality.get("provenance", ProvenanceStatus.PARTIAL.value))
    )
    missing_sources = tuple(str(value) for value in data_quality.get("missing_sources", []))
    censoring_reasons = tuple(str(value) for value in data_quality.get("censoring_reasons", []))
    notes = [
        f"freeze_seq={freeze_row.get('freeze_seq')}",
        f"frozen_via={freeze_row.get('frozen_via')}",
    ]
    slate = SlateDossier(
        slate_identity=SlateIdentity(
            slate_id=slate_date,
            contest_id=str(results_rows[0]["contest_id"] if results_rows else slate_date),
            slate_date=slate_date,
            sport="wnba",
            contest_name=f"WNBA Real Sports slate {slate_date}",
            league="WNBA",
        ),
        knowledge_state=KnowledgeState(
            as_of=_utc_iso(freeze_row.get("frozen_at")) or slate_date,
            decision_cutoff_at=_utc_iso(audit.get("slate_meta", {}).get("contest_lock_utc")),
            artifact_id=str(freeze_row.get("model_sha") or ""),
            artifact_version=str(freeze_row.get("model_sha") or ""),
            notes=tuple(notes),
        ),
        feasible_action_family=FeasibleActionFamily(
            ordered_slots=tuple(f"slot_{index}" for index in range(1, 6)),
            constraints=(
                FeasibilityConstraint(name="entry_size", value=5),
                FeasibilityConstraint(
                    name="max_per_team",
                    value=audit.get("optimizer", {}).get("serving_knobs", {}).get("max_per_team"),
                ),
            ),
            max_from_one_group=_int(
                audit.get("optimizer", {}).get("serving_knobs", {}).get("max_per_team")
            ),
            summary="Real Sports five-card WNBA slate in committed slot order.",
        ),
        our_committed_entry=SlateEntry(
            achievability=Achievability.OUR_COMMITTED,
            slots=committed_slots,
            entry_id=str(freeze_row.get("id") or ""),
            label="our_committed_entry",
            realized_score=legacy_dossier.entries[EntryKind.COMMITTED].score,
            realized_payout=payout,
            payout_currency="USD" if payout is not None else None,
            rank=our_rank,
            provenance=provenance,
            censoring_reason=(censoring_reasons[0] if censoring_reasons else None),
            slot_order_basis="committed",
        ),
        best_observed_field_entry=SlateEntry(
            achievability=Achievability.OBSERVED_FIELD,
            slots=field_slots,
            entry_id=str(field_entry.get("entry_id") or ""),
            label="best_observed_field_entry",
            realized_score=legacy_dossier.entries[EntryKind.FIELD_BEST].score,
            rank=_int(field_entry.get("rank")),
            provenance=provenance,
            censoring_reason=(censoring_reasons[0] if censoring_reasons else None),
            slot_order_basis="as_entered",
        ),
        theoretical_best_entry=SlateEntry(
            achievability=Achievability.THEORETICAL_HINDSIGHT_UPPER_BOUND,
            slots=theoretical_slots,
            entry_id=f"theoretical:{slate_date}",
            label="theoretical_best_entry",
            realized_score=legacy_dossier.entries[EntryKind.THEORETICAL_CEILING].score,
            provenance=ProvenanceStatus.PARTIAL,
            censoring_reason=(censoring_reasons[0] if censoring_reasons else None),
            slot_order_basis="optimal_resort",
        ),
        gap_analysis=build_gap_analysis(
            SlateEntry(
                achievability=Achievability.OUR_COMMITTED,
                slots=committed_slots,
                realized_score=legacy_dossier.entries[EntryKind.COMMITTED].score,
                provenance=provenance,
            ),
            SlateEntry(
                achievability=Achievability.OBSERVED_FIELD,
                slots=field_slots,
                realized_score=legacy_dossier.entries[EntryKind.FIELD_BEST].score,
                provenance=provenance,
            ),
            SlateEntry(
                achievability=Achievability.THEORETICAL_HINDSIGHT_UPPER_BOUND,
                slots=theoretical_slots,
                realized_score=legacy_dossier.entries[EntryKind.THEORETICAL_CEILING].score,
                provenance=ProvenanceStatus.PARTIAL,
            ),
        ),
        realized_outcomes=RealizedOutcomes(
            settled=bool(results_rows),
            settled_at=_utc_iso(results_rows[0].get("ingested_at")) if results_rows else None,
            field_size=field_size,
            our_rank=our_rank,
            our_percentile=our_percentile,
            notes=("leaderboard top row captured",) if field_entry else (),
        ),
        data_quality_and_censoring=DataQualityAndCensoring(
            provenance=provenance,
            leaderboard_capture_depth=len(leaderboard_rows) or None,
            observed_entry_count=field_size,
            missing_sources=missing_sources,
            censoring_reasons=censoring_reasons,
            note=data_quality.get("note"),
        ),
        learning_summary=LearningSummary(
            summary="Shared SlateDossier view over the WNBA local dossier and lineage audit.",
            takeaways=(
                audit.get("input_snapshot", {}).get("status", "unknown_input_snapshot"),
                audit.get("prediction_paths", {}).get("status", "unknown_prediction_paths"),
            ),
            follow_ups=tuple(filter(None, [audit.get("input_snapshot", {}).get("follow_up")])),
        ),
    )
    return slate.to_dict()


def build_slate_audit(
    slate_date: str,
    model_sha: str = "",
    *,
    engine: Any | None = None,
) -> dict[str, Any] | None:
    eng = engine or get_api_engine()
    with eng.connect() as conn:
        freeze_row = conn.execute(
            _FREEZE_Q, {"slate_date": slate_date, "model_sha": model_sha}
        ).first()
        if freeze_row is None:
            return None
        freeze = dict(freeze_row._mapping)
        enrichment_rows = _load_rows(conn, _ENRICHMENT_Q, {"slate_date": slate_date})
        results_rows = _load_rows(conn, _RESULTS_Q, {"slate_date": slate_date})
        leaderboard_rows = _load_rows(conn, _LEADERBOARD_Q, {"slate_date": slate_date})
        placement_rows = _load_rows(conn, _PLACEMENT_Q, {"slate_date": slate_date})
        slate_meta_rows = _load_rows(conn, _SLATE_META_Q, {"slate_date": slate_date})
        all_freezes = _load_rows(conn, _ALL_FREEZES_Q, {"slate_date": slate_date})
        snapshot = _load_snapshot_payload(
            conn, str(freeze.get("audit_snapshot_sha256") or "") or None
        )

    lineup_payload = _mapping(freeze.get("lineup"))
    metadata_json = _mapping(freeze.get("metadata_json"))
    model_provenance = _mapping(lineup_payload.get("model_provenance"))
    source_assurance = _mapping(lineup_payload.get("source_assurance"))
    serving_knobs = _mapping(lineup_payload.get("serving_knobs"))
    payout_curve = _mapping(lineup_payload.get("payout_curve"))
    stack_decision = _mapping(lineup_payload.get("stack_decision"))
    artifact_contract = _load_artifact_contract(str(freeze.get("model_sha") or ""))
    prediction_rows = _prediction_path_rows(snapshot["payload_json"] if snapshot else None)
    if enrichment_rows:
        with eng.connect() as identity_conn:
            identity_rows = _identity_resolution_rows(identity_conn, enrichment_rows)
    else:
        identity_rows = []
    input_snapshot = _current_enrichment_reconstruction(
        enrichment_rows,
        model_provenance,
        snapshot=snapshot,
    )
    missing_sources: list[str] = []
    if not results_rows:
        missing_sources.append("slate_labels")
    if not leaderboard_rows:
        missing_sources.append("contest_leaderboards")
    if not identity_rows:
        missing_sources.append("canonical_player_identities")
    if artifact_contract.get("status") != "available":
        missing_sources.append("model_artifact")
    if snapshot is None:
        missing_sources.append("freeze_audit_snapshot")
    censoring_reasons: list[str] = []
    if input_snapshot.get("status") == "current_rows_do_not_match_freeze":
        censoring_reasons.append("historical_job1_state_mutated_since_freeze")
    if not results_rows:
        censoring_reasons.append("realized_results_pending")
    if not leaderboard_rows:
        censoring_reasons.append("leaderboard_unavailable")
    if snapshot is None:
        censoring_reasons.append("prediction_paths_not_captured_pre_issue35")
    provenance = (
        ProvenanceStatus.EXACT
        if not missing_sources and not censoring_reasons
        else ProvenanceStatus.PARTIAL
        if results_rows or leaderboard_rows
        else ProvenanceStatus.UNAVAILABLE
    )
    freeze_history = [
        {
            **row,
            "frozen_at": _utc_iso(row.get("frozen_at")),
        }
        for row in all_freezes
    ]
    slate_meta = slate_meta_rows[0] if slate_meta_rows else {}
    if slate_meta:
        slate_meta = {
            **slate_meta,
            "first_tip_utc": _utc_iso(slate_meta.get("first_tip_utc")),
            "contest_lock_utc": _utc_iso(slate_meta.get("contest_lock_utc")),
            "updated_at": _utc_iso(slate_meta.get("updated_at")),
        }
    prediction_section: dict[str, Any]
    if snapshot is not None:
        prediction_section = {
            "status": "captured_in_immutable_snapshot",
            "rows": prediction_rows,
        }
    else:
        prediction_section = {
            "status": "not_captured",
            "reason": "per-player prediction tier and serve-contract details were not persisted before issue #35 phase 2",
            "rows": [],
        }
    placement = placement_rows[0] if placement_rows else None
    pool_ids = {
        pid
        for pid in (normalize_pid(row.get("real_sports_player_id")) for row in enrichment_rows)
        if pid is not None
    }
    resolved_ids = identity_map(identity_rows)
    contest_results = {
        "leaderboard_status": {
            "status": "available"
            if leaderboard_rows
            else "pending"
            if not results_rows
            else "unavailable",
            "reason": None if leaderboard_rows else "contest_leaderboards_not_captured_for_slate",
            "captured_rows": len(leaderboard_rows),
            "returned_rows": min(len(leaderboard_rows), 20),
        },
        "leaderboard": [
            {
                **row,
                "ingested_at": _utc_iso(row.get("ingested_at")),
            }
            for row in leaderboard_rows[:20]
        ],
        "placement": {
            **placement,
            "recorded_at": _utc_iso(placement.get("recorded_at")),
        }
        if placement
        else {
            "status": "unavailable",
            "reason": "contest placement has not been recorded for this slate",
        },
    }
    audit = {
        "slate_date": slate_date,
        "model_sha": freeze.get("model_sha"),
        "sources": {
            "realsports": source_status(source_assurance, "realsports"),
            "rotowire": source_status(source_assurance, "rotowire"),
            "the_odds_api": source_status(source_assurance, "the_odds_api"),
            "wnba_stats": source_status(source_assurance, "wnba_stats"),
            "model_artifact": artifact_contract,
            "identity_mapping": {
                "status": "available" if identity_rows else "unavailable",
                "rows": identity_rows,
                "coverage": {
                    "pool_players": len(pool_ids),
                    "resolved": len(pool_ids & set(resolved_ids)),
                    "unresolved": sorted(pool_ids - set(resolved_ids), key=_pid_sort_key),
                },
                "reason": None
                if identity_rows
                else "canonical identity mapping was not yet persisted or is unavailable in this schema",
            },
            "payout_archive": {
                "status": "available" if payout_curve else "not_captured",
                "reason": None if payout_curve else "frozen_lineups.lineup.payout_curve_absent",
                "source": "frozen_lineups.lineup.payout_curve",
            },
        },
        "input_snapshot": input_snapshot,
        "feature_and_signal_lineage": {
            "status": "available",
            "matrix": _static_signal_matrix(
                enrichment_rows=enrichment_rows,
                prediction_rows=prediction_rows,
            )
            + _artifact_feature_matrix(
                artifact_contract,
                enrichment_rows=enrichment_rows,
                prediction_rows=prediction_rows,
            ),
            "artifact_contract": artifact_contract,
        },
        "prediction_paths": prediction_section,
        "optimizer": {
            "status": "available" if model_provenance else "not_captured",
            "reason": None if model_provenance else "frozen_lineups.lineup.model_provenance_absent",
            "model_provenance": model_provenance,
            "serving_knobs": serving_knobs,
            "payout_curve": payout_curve,
            "stack_decision": stack_decision,
            "optimizer_input_hash": model_provenance.get("optimizer_inputs_sha256"),
            "model_policy_sha256": model_provenance.get("model_policy_sha256"),
        },
        "frozen_lineup": {
            "id": freeze.get("id"),
            "freeze_seq": freeze.get("freeze_seq"),
            "frozen_at": _utc_iso(freeze.get("frozen_at")),
            "frozen_via": freeze.get("frozen_via"),
            "operation_key": freeze.get("operation_key"),
            "entry_recommendation": freeze.get("entry_recommendation"),
            "expected_payout": _float(freeze.get("expected_payout")),
            "lineup": lineup_payload,
            "metadata_json": metadata_json,
            "freeze_history": freeze_history,
            "audit_snapshot_sha256": freeze.get("audit_snapshot_sha256"),
        },
        "realized_player_results": _results_sections(results_rows),
        "contest_results": contest_results,
        "our_outcome": {
            "status": "available"
            if placement
            else "pending"
            if not results_rows
            else "unavailable",
            "reason": None if placement else "contest_placements_row_not_recorded_for_slate",
            "entry_rank": _int(placement.get("entry_rank")) if placement else None,
            "entry_count": _int(placement.get("entry_count")) if placement else None,
            "entry_score": _float(placement.get("entry_score")) if placement else None,
            "payout_received": (
                _cents_to_dollars(placement.get("payout_received_cents")) if placement else None
            ),
            "entry_fee": (
                _cents_to_dollars(placement.get("entry_fee_cents")) if placement else None
            ),
            "finish_percentile": _float(placement.get("finish_percentile")) if placement else None,
            "roi": _float(placement.get("roi")) if placement else None,
        },
        "data_quality_and_censoring": {
            "provenance": provenance.value,
            "missing_sources": missing_sources,
            "censoring_reasons": censoring_reasons,
            "note": (
                "Historical exact input state is only exact when current job1_enrichment hashes still match the stored freeze provenance, or when the new issue #35 snapshot reference is present."
            ),
        },
        "slate_meta": slate_meta,
    }
    legacy = build_dossier(slate_date, engine=eng)
    if legacy is not None:
        audit["legacy_dossier"] = legacy.to_dict()
        shared = _shared_slate_dossier(
            slate_date=slate_date,
            freeze_row=freeze,
            legacy_dossier=legacy,
            results_rows=results_rows,
            leaderboard_rows=leaderboard_rows,
            placement_row=placement,
            audit=audit,
        )
        if shared is not None:
            audit["shared_slate_dossier"] = shared
    return audit


def build_post_slate_dossier(
    slate_date: str,
    model_sha: str = "",
    *,
    engine: Any | None = None,
) -> dict[str, Any] | None:
    audit = build_slate_audit(slate_date, model_sha, engine=engine)
    if audit is None:
        return None
    payload: dict[str, Any] = {}
    legacy = audit.get("legacy_dossier")
    realized = audit.get("realized_player_results") or {}
    if isinstance(legacy, Mapping):
        payload.update(dict(legacy))
        payload["entries_status"] = {"status": "available", "reason": None}
    else:
        payload["entries_status"] = {
            "status": "pending" if realized.get("status") != "available" else "unavailable",
            "reason": (
                "committed/field_best/theoretical_ceiling entries require a frozen lineup, "
                "a captured contest leaderboard, and realized slate_labels"
            ),
        }
    payload.update(
        {
            "slate_date": slate_date,
            "model_sha": audit.get("model_sha"),
            "shared_slate_dossier": audit.get("shared_slate_dossier"),
            "sources": audit.get("sources"),
            "input_snapshot": audit.get("input_snapshot"),
            "feature_and_signal_lineage": audit.get("feature_and_signal_lineage"),
            "prediction_paths": audit.get("prediction_paths"),
            "optimizer": audit.get("optimizer"),
            "frozen_lineup": audit.get("frozen_lineup"),
            "realized_player_results": audit.get("realized_player_results"),
            "contest_results": audit.get("contest_results"),
            "our_outcome": audit.get("our_outcome"),
            "data_quality_and_censoring": audit.get("data_quality_and_censoring"),
            "slate_meta": audit.get("slate_meta"),
        }
    )
    frozen_lineup = audit.get("frozen_lineup") or {}
    lineup_payload = _mapping(frozen_lineup.get("lineup"))
    selected_ids = [
        pid
        for pid in (normalize_pid(value) for value in _sequence(lineup_payload.get("player_ids")))
        if pid is not None
    ]
    eng = engine or get_api_engine()
    identity_rows = list(
        _sequence((audit.get("sources") or {}).get("identity_mapping", {}).get("rows"))
    )
    mapping = identity_map(identity_rows)
    # The pool identity lookup is keyed off job1_enrichment; when those rows
    # are gone (retention, purge) the committed five would otherwise read as
    # identity_unresolved even though canonical_player_identities has them.
    unmapped = [pid for pid in selected_ids if pid not in mapping]
    if unmapped:
        with eng.connect() as identity_conn:
            identity_rows.extend(
                _identity_resolution_rows(
                    identity_conn, [{"real_sports_player_id": pid} for pid in unmapped]
                )
            )
        mapping = identity_map(identity_rows)
    wnba_ids = [mapping[pid] for pid in selected_ids if pid in mapping]
    game_log_rows, game_log_error = load_game_logs(eng, slate_date, wnba_ids)
    prediction_paths = audit.get("prediction_paths") or {}
    snapshot_players = (
        _sequence(prediction_paths.get("rows"))
        if prediction_paths.get("status") == "captured_in_immutable_snapshot"
        else None
    )
    return finalize_dossier(
        payload,
        snapshot_players=snapshot_players,
        result_rows=_sequence(realized.get("rows")),
        game_log_rows=game_log_rows,
        game_log_error=game_log_error,
        identity_rows=identity_rows,
    )


def _pid_sort_key(value: str) -> tuple[int, str]:
    try:
        return (int(value), value)
    except ValueError:
        return (1 << 62, value)
