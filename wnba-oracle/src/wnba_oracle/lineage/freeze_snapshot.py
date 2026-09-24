"""Immutable freeze-audit snapshot capture for new WNBA freezes."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping, Sequence
from typing import Any

from oracle_core.artifacts import sha256_bytes
from sqlalchemy import text

from wnba_oracle.common.feature_payload import parse_feature_mapping
from wnba_oracle.scheduler.job2_model import REPO_ROOT, _load_model_artifact

FREEZE_AUDIT_SNAPSHOT_SCHEMA_VERSION = 1

FREEZE_AUDIT_SNAPSHOT_INSERT = text(
    """
    INSERT INTO freeze_audit_snapshots (
        snapshot_sha256,
        schema_version,
        payload_json,
        created_at
    ) VALUES (
        :snapshot_sha256,
        :schema_version,
        CAST(:payload_json AS JSONB),
        now()
    )
    ON CONFLICT (snapshot_sha256) DO NOTHING
    """
)

FREEZE_AUDIT_SNAPSHOT_SELECT = text(
    """
    SELECT snapshot_sha256, schema_version, payload_json, created_at
    FROM freeze_audit_snapshots
    WHERE snapshot_sha256 = :snapshot_sha256
    """
)

_CANONICAL_IDENTITY_Q = text(
    """
    SELECT real_sports_player_id, wnba_player_id, provenance, provider_nba_id,
           real_sports_display_name, real_sports_team, wnba_full_name,
           first_seen_at, last_seen_at
    FROM canonical_player_identities
    WHERE real_sports_player_id = ANY(:real_sports_ids)
    """
)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


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


def _float_or_none(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _identity_rows(conn: Any, real_sports_ids: Sequence[str]) -> dict[str, dict[str, Any]]:
    if not real_sports_ids:
        return {}
    try:
        rows = conn.execute(
            _CANONICAL_IDENTITY_Q, {"real_sports_ids": list(real_sports_ids)}
        ).fetchall()
    except Exception:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        mapping = dict(row._mapping)
        out[str(mapping["real_sports_player_id"])] = {
            "status": "available",
            "real_sports_player_id": str(mapping["real_sports_player_id"]),
            "wnba_player_id": int(mapping["wnba_player_id"]),
            "provenance": mapping.get("provenance"),
            "provider_nba_id": mapping.get("provider_nba_id"),
            "real_sports_display_name": mapping.get("real_sports_display_name"),
            "real_sports_team": mapping.get("real_sports_team"),
            "wnba_full_name": mapping.get("wnba_full_name"),
            "first_seen_at": _utc_iso(mapping.get("first_seen_at")),
            "last_seen_at": _utc_iso(mapping.get("last_seen_at")),
        }
    return out


def _artifact_contract(model_sha: str) -> dict[str, Any]:
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
            "calibrators_consumed_at_serving": bool(
                getattr(art, "calibrators_consumed_at_serving", False)
            ),
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
            "calibrators_consumed_at_serving": payload.get("calibrators_consumed_at_serving"),
        }
    return {
        "status": "unavailable",
        "artifact_sha256": model_sha,
        "reason": "artifact_not_present_in_workspace",
    }


def _serve_contract_for_player(
    *,
    row: Mapping[str, Any],
    prediction_audit: Mapping[str, Any],
    artifact_contract: Mapping[str, Any],
) -> dict[str, Any]:
    if artifact_contract.get("status") != "available":
        return {
            "status": "artifact_unavailable",
            "artifact_sha256": artifact_contract.get("artifact_sha256"),
        }

    features, _ = parse_feature_mapping(row.get("features_json"))
    head_features = features.get("head_features") if isinstance(features, dict) else None
    head_features = head_features if isinstance(head_features, Mapping) else {}
    tier = str(prediction_audit.get("tier") or "")
    subset = artifact_contract.get("feature_subset_per_head")
    if not isinstance(subset, Mapping):
        subset = {}
    consumed: list[str] = []
    for key in ("minutes:F", "real_score_per_min:F"):
        columns = subset.get(key)
        if isinstance(columns, list):
            consumed.extend(str(column) for column in columns)
    consumed = list(dict.fromkeys(consumed))
    if tier != "trained_heads":
        return {
            "status": "not_consumed",
            "reason": "head_tier_not_used",
            "tier": tier or None,
            "artifact_feature_columns": consumed,
        }
    provided = [column for column in consumed if column in head_features]
    defaulted = [column for column in consumed if column not in head_features]
    return {
        "status": "consumed",
        "tier": tier,
        "artifact_feature_columns": consumed,
        "provided_feature_columns": provided,
        "defaulted_feature_columns": defaulted,
        "serve_values": {
            column: _float_or_none(head_features.get(column, 0.0)) for column in consumed
        },
    }


def build_freeze_audit_snapshot(
    *,
    slate_date: str,
    model_sha: str,
    frozen_at: dt.datetime,
    enrichment_rows: Sequence[Mapping[str, Any]],
    projection_by_pid: Mapping[int, Mapping[str, Any]],
    scoring_provenance: Mapping[str, Any],
    source_assurance: Mapping[str, Any],
    freeze_context: Mapping[str, Any],
    conn: Any | None = None,
) -> dict[str, Any]:
    """Build the immutable, content-addressed snapshot payload for one freeze."""

    artifact_contract = _artifact_contract(model_sha)
    real_sports_ids = [
        str(row.get("real_sports_player_id") or "").strip() for row in enrichment_rows
    ]
    real_sports_ids = [player_id for player_id in real_sports_ids if player_id]
    identity_rows = _identity_rows(conn, real_sports_ids) if conn is not None else {}

    players: list[dict[str, Any]] = []
    for row in enrichment_rows:
        player_id = str(row.get("real_sports_player_id") or "").strip()
        if not player_id:
            continue
        try:
            projection = projection_by_pid.get(int(player_id), {})
        except ValueError:
            projection = {}
        prediction_audit = projection.get("_prediction_audit")
        prediction_audit = prediction_audit if isinstance(prediction_audit, Mapping) else {}
        identity_snapshot = identity_rows.get(player_id)
        if identity_snapshot is None:
            identity_snapshot = {
                "status": "unavailable",
                "reason": "not_captured_in_current_schema",
            }
        players.append(
            {
                "real_sports_player_id": player_id,
                "display_name": projection.get("display_name") or row.get("name"),
                "team": row.get("team"),
                "opponent": row.get("opponent"),
                "position": row.get("position"),
                "card_boost": _float_or_none(row.get("card_boost")),
                "captured_at_utc": _utc_iso(row.get("captured_at")),
                "features_json": row.get("features_json"),
                "prediction_path": dict(prediction_audit),
                "serve_contract": _serve_contract_for_player(
                    row=row,
                    prediction_audit=prediction_audit,
                    artifact_contract=artifact_contract,
                ),
                "identity_resolution": identity_snapshot,
            }
        )
    players.sort(key=lambda player: int(str(player["real_sports_player_id"])))
    payload = {
        "schema_version": FREEZE_AUDIT_SNAPSHOT_SCHEMA_VERSION,
        "slate_date": slate_date,
        "model_sha": model_sha,
        "frozen_at_utc": frozen_at.astimezone(dt.UTC).isoformat(),
        "scoring_provenance": dict(scoring_provenance),
        "source_assurance": dict(source_assurance),
        "freeze_context": dict(freeze_context),
        "artifact_contract": artifact_contract,
        "players": players,
    }
    return payload


def persist_freeze_audit_snapshot(conn: Any, payload: Mapping[str, Any]) -> str:
    body = dict(payload)
    snapshot_sha256 = sha256_bytes(_canonical_json(body))
    conn.execute(
        FREEZE_AUDIT_SNAPSHOT_INSERT,
        {
            "snapshot_sha256": snapshot_sha256,
            "schema_version": int(body.get("schema_version", FREEZE_AUDIT_SNAPSHOT_SCHEMA_VERSION)),
            "payload_json": json.dumps(
                body, sort_keys=True, separators=(",", ":"), allow_nan=False
            ),
        },
    )
    return snapshot_sha256
