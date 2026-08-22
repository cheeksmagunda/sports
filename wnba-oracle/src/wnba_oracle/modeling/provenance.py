"""Canonical model-ingress fingerprints for replay and drift diagnosis."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, ClassVar

from wnba_oracle.modeling.policy import ModelPolicy
from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.payout import PayoutCurve
from wnba_oracle.picker.sample import PlayerSamplingSpec

MODEL_ENGINE_VERSION = "1"

_ENRICHMENT_FIELDS = (
    "real_sports_player_id",
    "name",
    "team",
    "opponent",
    "position",
    "card_boost",
    "features_json",
)


def _normalize_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Decimal):
        return float(value) if value.is_finite() else {"decimal": str(value)}
    if isinstance(value, float):
        return value if math.isfinite(value) else {"float": str(value)}
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_json(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, Sequence):
        return [_normalize_json(item) for item in value]
    return {"type": type(value).__name__, "value": str(value)}


def _features_payload(value: Any) -> Any:
    if isinstance(value, (bytes, str)) and value:
        try:
            decoded = value.decode("utf-8") if isinstance(value, bytes) else value
            value = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"invalid_json": _normalize_json(value)}
    return _normalize_json(value)


def _player_id(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, str, bytes, bytearray, Decimal)):
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError):
            return None
    return None


def _enrichment_records(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    players: list[dict[str, Any]] = []
    for row in rows:
        record = {field: _normalize_json(row.get(field)) for field in _ENRICHMENT_FIELDS}
        record["features_json"] = _features_payload(row.get("features_json"))
        record["real_sports_player_id"] = _player_id(row.get("real_sports_player_id"))
        players.append(record)
    return players


def _json_payload(value: Any) -> bytes:
    return json.dumps(
        _normalize_json(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def enrichment_sequence_payload(rows: Sequence[Mapping[str, Any]]) -> bytes:
    """Serialize model ingress while retaining incumbent adapter row order."""
    return _json_payload({"schema_version": 1, "players": _enrichment_records(rows)})


def canonical_enrichment_payload(rows: Sequence[Mapping[str, Any]]) -> bytes:
    """Serialize consumed enrichment fields independently of adapter ordering.

    This is observational in phase one: production scoring keeps its incumbent
    row order, while the canonical digest exposes whether the same semantic
    input reached a replay, shadow, or future adapter.
    """
    players = _enrichment_records(rows)

    def sort_key(record: dict[str, Any]) -> tuple[bool, int, str]:
        player_id = record["real_sports_player_id"]
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return (player_id is None, int(player_id or 0), canonical)

    players.sort(key=sort_key)
    return _json_payload({"schema_version": 1, "players": players})


def optimizer_input_payload(
    sampling_specs: Sequence[PlayerSamplingSpec],
    field_specs: Sequence[FieldPlayerSpec],
    payout_curve: PayoutCurve,
) -> bytes:
    """Serialize the exact finalized inputs consumed by the optimizer."""
    return _json_payload(
        {
            "schema_version": 1,
            "sampling_specs": [asdict(spec) for spec in sampling_specs],
            "field_specs": [asdict(spec) for spec in field_specs],
            "payout_curve": asdict(payout_curve),
        }
    )


@dataclass(frozen=True)
class ScoringProvenance:
    """Verification manifest persisted with the incumbent model decision."""

    SCHEMA_VERSION: ClassVar[int] = 1

    model_policy: ModelPolicy
    enrichment_sha256: str
    enrichment_sequence_sha256: str
    enrichment_rows: int
    optimizer_inputs_sha256: str
    optimizer_players: int
    optimizer_inputs: dict[str, Any]
    artifact_loaded: bool
    artifact_feature_module_sha: str | None
    serving_feature_module_sha: str | None

    @classmethod
    def capture(
        cls,
        *,
        model_policy: ModelPolicy,
        enrichment: Sequence[Mapping[str, Any]],
        sampling_specs: Sequence[PlayerSamplingSpec],
        field_specs: Sequence[FieldPlayerSpec],
        payout_curve: PayoutCurve,
        artifact_loaded: bool = False,
        artifact_feature_module_sha: str | None = None,
        serving_feature_module_sha: str | None = None,
    ) -> ScoringProvenance:
        canonical = canonical_enrichment_payload(enrichment)
        sequence = enrichment_sequence_payload(enrichment)
        optimizer_inputs = optimizer_input_payload(
            sampling_specs,
            field_specs,
            payout_curve,
        )
        return cls(
            model_policy=model_policy,
            enrichment_sha256=hashlib.sha256(canonical).hexdigest(),
            enrichment_sequence_sha256=hashlib.sha256(sequence).hexdigest(),
            enrichment_rows=len(enrichment),
            optimizer_inputs_sha256=hashlib.sha256(optimizer_inputs).hexdigest(),
            optimizer_players=len(sampling_specs),
            optimizer_inputs=json.loads(optimizer_inputs),
            artifact_loaded=artifact_loaded,
            artifact_feature_module_sha=artifact_feature_module_sha,
            serving_feature_module_sha=serving_feature_module_sha,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "model_engine_version": MODEL_ENGINE_VERSION,
            "model_policy_sha256": self.model_policy.sha256,
            "model_policy": self.model_policy.to_payload(),
            "enrichment_schema_version": 1,
            "enrichment_sha256": self.enrichment_sha256,
            "enrichment_sequence_sha256": self.enrichment_sequence_sha256,
            "enrichment_rows": self.enrichment_rows,
            "optimizer_inputs_schema_version": 1,
            "optimizer_inputs_sha256": self.optimizer_inputs_sha256,
            "optimizer_players": self.optimizer_players,
            "optimizer_inputs": self.optimizer_inputs,
            "artifact_loaded": self.artifact_loaded,
            "artifact_feature_module_sha": self.artifact_feature_module_sha,
            "serving_feature_module_sha": self.serving_feature_module_sha,
            "artifact_feature_module_match": (
                self.artifact_feature_module_sha == self.serving_feature_module_sha
                if self.artifact_feature_module_sha is not None
                and self.serving_feature_module_sha is not None
                else None
            ),
            "canonical_order_active": False,
        }
