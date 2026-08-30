"""Observational source-quality facts attached to a frozen recommendation.

This module consumes a copy of the enrichment rows after recommendation math
has completed. It reports only aggregate evidence, timestamps, stable connector
IDs, and content hashes. It never receives credentials and never decides which
players to score or select.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, Final

from wnba_oracle.assurance.connectors import (
    DECISION_INPUT_CONNECTOR_CATALOG_SHA256,
    DECISION_INPUT_CONNECTOR_IDS,
)
from wnba_oracle.common.feature_payload import parse_feature_mapping

SOURCE_ASSURANCE_SCHEMA_VERSION: Final = 2
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TRIGGER_RE = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_ERROR_TYPE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,79}$")
_ALLOWED_POSITIONS = frozenset({"G", "F", "C", "G-F", "F-G", "F-C", "C-F"})


def _utc_datetime(value: object) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def _utc_iso(value: object) -> str | None:
    parsed = _utc_datetime(value)
    return parsed.isoformat() if parsed is not None else None


def _safe_sha256(value: object) -> str | None:
    candidate = str(value or "").strip().lower()
    return candidate if _SHA256_RE.fullmatch(candidate) else None


def _safe_error_type(value: object) -> str:
    candidate = str(value or "AssuranceError").strip()
    return candidate if _ERROR_TYPE_RE.fullmatch(candidate) else "AssuranceError"


def _features(value: object) -> tuple[dict[str, Any], bool]:
    return parse_feature_mapping(value)


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float, str, bytes, bytearray, Decimal),
    ):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _positive_player_id(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float, str, bytes, bytearray, Decimal),
    ):
        return False
    try:
        return int(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def _source_counts(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], int, int]:
    total = len(rows)
    core_rows = 0
    invalid_features_rows = 0
    game_time_rows = 0
    starter_rows = 0
    confirmed_rows = 0
    vegas_rows = 0
    prop_rows = 0
    minutes_rows = 0
    head_feature_rows = 0
    captured: list[dt.datetime] = []
    teams: set[str] = set()

    for row in rows:
        team = str(row.get("team") or "").strip()
        if team:
            teams.add(team)
        position = str(row.get("position") or "").strip()
        boost = _finite_number(row.get("card_boost"))
        if (
            _positive_player_id(row.get("real_sports_player_id"))
            and bool(str(row.get("name") or "").strip())
            and bool(team)
            and position in _ALLOWED_POSITIONS
            and boost is not None
            and 0.0 <= boost <= 5.0
        ):
            core_rows += 1

        captured_at = _utc_datetime(row.get("captured_at"))
        if captured_at is not None:
            captured.append(captured_at)

        features, invalid = _features(row.get("features_json"))
        invalid_features_rows += int(invalid)
        game_time_rows += int(bool(str(features.get("game_start_utc") or "").strip()))
        starter_rows += int(bool(features.get("is_starter")))
        confirmed_rows += int(bool(features.get("rotowire_confirmed")))
        vegas_total = _finite_number(features.get("vegas_total"))
        vegas_rows += int(vegas_total is not None and vegas_total > 0.0)
        prop_rows += int(
            any(
                key.startswith("prop_")
                and key.endswith("_line")
                and _finite_number(value) is not None
                for key, value in features.items()
            )
        )
        recent_minutes = _finite_number(features.get("recent_minutes"))
        per_min_rate = _finite_number(features.get("per_min_rate"))
        minutes_rows += int(
            recent_minutes is not None
            and recent_minutes >= 0.0
            and per_min_rate is not None
            and per_min_rate >= 0.0
        )
        head_feature_rows += int(
            isinstance(features.get("head_features"), Mapping) and bool(features["head_features"])
        )

    first_captured = min(captured).isoformat() if captured else None
    last_captured = max(captured).isoformat() if captured else None
    payload = {
        "capture": {
            "rows": total,
            "teams": len(teams),
            "captured_at_rows": len(captured),
            "first_captured_at_utc": first_captured,
            "last_captured_at_utc": last_captured,
            "invalid_features_json_rows": invalid_features_rows,
        },
        "observations": {
            "postgres": {
                "enrichment_rows": total,
                "captured_at_rows": len(captured),
            },
            "realsports": {
                "core_rows": core_rows,
                "game_time_rows": game_time_rows,
            },
            "rotowire": {
                "starter_rows": starter_rows,
                "confirmed_rows": confirmed_rows,
            },
            "the_odds_api": {
                "vegas_rows": vegas_rows,
                "prop_rows": prop_rows,
            },
            "wnba_stats": {
                "minutes_rows": minutes_rows,
                "head_feature_rows": head_feature_rows,
            },
        },
    }
    return payload, core_rows, invalid_features_rows


def unknown_source_assurance(
    *,
    assessed_at: object,
    decision_input_sha256: object,
    decision_input_canonical_sha256: object,
    error_type: object,
) -> dict[str, Any]:
    """Return a value-free failure record that cannot expose exception text."""

    return {
        "schema_version": SOURCE_ASSURANCE_SCHEMA_VERSION,
        "decision_input_connector_catalog_sha256": (DECISION_INPUT_CONNECTOR_CATALOG_SHA256),
        "decision_input_connector_ids": list(DECISION_INPUT_CONNECTOR_IDS),
        "assessment_status": "unknown",
        "assessed_at_utc": _utc_iso(assessed_at),
        "decision_input_sha256": _safe_sha256(decision_input_sha256),
        "decision_input_canonical_sha256": _safe_sha256(decision_input_canonical_sha256),
        "error": {"type": _safe_error_type(error_type)},
    }


def _build_source_assurance(
    rows: Sequence[Mapping[str, Any]],
    *,
    assessed_at: object,
    decision_input_sha256: object,
    decision_input_canonical_sha256: object,
    finding_triggers: Sequence[str],
) -> dict[str, Any]:
    digest = _safe_sha256(decision_input_sha256)
    if digest is None:
        raise ValueError("decision input digest must be SHA-256")
    canonical_digest = _safe_sha256(decision_input_canonical_sha256)
    if canonical_digest is None:
        raise ValueError("canonical decision input digest must be SHA-256")
    assessed_at_utc = _utc_iso(assessed_at)
    if assessed_at_utc is None:
        raise ValueError("assessed_at must be an ISO timestamp")

    sanitized_triggers = sorted(
        {
            trigger
            for trigger in finding_triggers
            if isinstance(trigger, str) and _TRIGGER_RE.fullmatch(trigger)
        }
    )
    counts, core_rows, invalid_features_rows = _source_counts(rows)
    if not rows:
        assessment_status = "unknown"
    elif sanitized_triggers or core_rows != len(rows) or invalid_features_rows:
        assessment_status = "degraded"
    else:
        assessment_status = "observed"
    return {
        "schema_version": SOURCE_ASSURANCE_SCHEMA_VERSION,
        "decision_input_connector_catalog_sha256": (DECISION_INPUT_CONNECTOR_CATALOG_SHA256),
        "decision_input_connector_ids": list(DECISION_INPUT_CONNECTOR_IDS),
        "assessment_status": assessment_status,
        "assessed_at_utc": assessed_at_utc,
        # The primary binding retains exact adapter row order because the
        # incumbent optimizer can be order-sensitive. The canonical digest is
        # also retained for order-independent replay and drift comparison.
        "decision_input_sha256": digest,
        "decision_input_canonical_sha256": canonical_digest,
        **counts,
        "finding_triggers": sanitized_triggers,
    }


def build_source_assurance(
    rows: Sequence[Mapping[str, Any]],
    *,
    assessed_at: object,
    decision_input_sha256: object,
    decision_input_canonical_sha256: object,
    finding_triggers: Sequence[str] = (),
    assessment_error_type: str | None = None,
) -> dict[str, Any]:
    """Build an observational manifest and convert every failure to unknown."""

    if assessment_error_type is not None:
        return unknown_source_assurance(
            assessed_at=assessed_at,
            decision_input_sha256=decision_input_sha256,
            decision_input_canonical_sha256=decision_input_canonical_sha256,
            error_type=assessment_error_type,
        )
    try:
        return _build_source_assurance(
            rows,
            assessed_at=assessed_at,
            decision_input_sha256=decision_input_sha256,
            decision_input_canonical_sha256=decision_input_canonical_sha256,
            finding_triggers=finding_triggers,
        )
    except Exception as exc:
        return unknown_source_assurance(
            assessed_at=assessed_at,
            decision_input_sha256=decision_input_sha256,
            decision_input_canonical_sha256=decision_input_canonical_sha256,
            error_type=type(exc).__name__,
        )
