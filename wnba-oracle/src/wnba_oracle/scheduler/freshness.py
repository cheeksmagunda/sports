"""Fail-closed readiness checks for publishing a WNBA lineup.

This is deliberately WNBA-owned. The required inputs are domain signals, not
provider-neutral infrastructure. The assessment is pure and returns only
value-free counts and reasons so callers can persist an operational decision
without exposing player data or credentials.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Any, cast

from wnba_oracle.common.feature_payload import parse_feature_mapping
from wnba_oracle.picker.field import FieldPlayerSpec, project_ownership

DEFAULT_MAX_CAPTURE_AGE_MINUTES = 6 * 60
DEFAULT_MIN_MINUTES_COVERAGE = 0.80


@dataclass(frozen=True)
class FreshnessAssessment:
    ready: bool
    reasons: tuple[str, ...]
    metrics: dict[str, object]


def _as_utc(value: object) -> dt.datetime | None:
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


def _finite_nonnegative(value: object) -> bool:
    try:
        number = float(cast("Any", value))
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(number) and number >= 0.0


def assess_publish_freshness(
    enrichment: list[dict],
    *,
    projection_by_pid: dict[int, dict],
    field_specs: list[FieldPlayerSpec],
    lock_time: dt.datetime | None,
    now_utc: dt.datetime,
    max_capture_age_minutes: int = DEFAULT_MAX_CAPTURE_AGE_MINUTES,
    min_minutes_coverage: float = DEFAULT_MIN_MINUTES_COVERAGE,
) -> FreshnessAssessment:
    """Assess whether a computed lineup is safe to publish.

    Projected ownership is the valid pre-lock signal. Measured ownership is
    optional and remains a calibration input. Minutes require both recent
    minutes and per-minute rate coverage for most of the pool; a zero-coverage
    slate cannot silently fall through to heuristic projections.
    """
    reasons: list[str] = []
    metrics: dict[str, object] = {"pool_rows": len(enrichment)}
    now = _as_utc(now_utc)
    lock = _as_utc(lock_time)

    if lock is None:
        reasons.append("slate_lock_missing")
    elif now is None or lock <= now:
        reasons.append("slate_lock_not_future")

    captures = [_as_utc(row.get("captured_at")) for row in enrichment]
    valid_captures = [value for value in captures if value is not None]
    metrics["captured_rows"] = len(valid_captures)
    metrics["capture_age_minutes"] = None
    if len(valid_captures) != len(enrichment):
        reasons.append("source_capture_missing")
    elif now is not None and valid_captures:
        age = max((now - value).total_seconds() / 60.0 for value in valid_captures)
        metrics["capture_age_minutes"] = round(age, 1)
        if age < 0 or age > max_capture_age_minutes:
            reasons.append("source_capture_stale")
    elif enrichment:
        reasons.append("source_capture_invalid")

    projection_ids = set(projection_by_pid)
    row_ids: set[int] = set()
    minutes_rows = 0
    injury_rows = 0
    for row in enrichment:
        try:
            pid = int(cast("Any", row.get("real_sports_player_id")))
        except (TypeError, ValueError, OverflowError):
            continue
        row_ids.add(pid)
        features, invalid = parse_feature_mapping(row.get("features_json"))
        if invalid:
            reasons.append("feature_payload_invalid")
        if (
            _finite_nonnegative(features.get("recent_minutes"))
            and _finite_nonnegative(features.get("per_min_rate"))
        ):
            minutes_rows += 1
        if "injury_status" in features:
            injury_rows += 1

    metrics["projection_rows"] = len(projection_ids)
    metrics["minutes_rows"] = minutes_rows
    metrics["minutes_coverage"] = round(minutes_rows / len(enrichment), 3) if enrichment else 0.0
    metrics["injury_rows"] = injury_rows
    metrics["injury_coverage"] = round(injury_rows / len(enrichment), 3) if enrichment else 0.0
    invalid_projections = sum(
        not _finite_nonnegative(projection.get("pred_real_score_p50"))
        for projection in projection_by_pid.values()
        if isinstance(projection, dict)
    )
    metrics["invalid_projections"] = invalid_projections
    if row_ids != projection_ids or invalid_projections:
        reasons.append("projection_missing")
    if enrichment and minutes_rows / len(enrichment) < min_minutes_coverage:
        reasons.append("minutes_coverage_insufficient")
    if enrichment and injury_rows != len(enrichment):
        reasons.append("injury_status_missing")

    metrics["ownership_rows"] = len(field_specs)
    try:
        ownership = project_ownership(field_specs)
        ownership_ok = (
            len(ownership) == len(field_specs)
            and all(math.isfinite(float(value)) and float(value) > 0.0 for value in ownership)
            and math.isclose(float(sum(ownership)), 1.0, rel_tol=1e-5, abs_tol=1e-5)
        )
    except Exception:
        ownership_ok = False
    if not ownership_ok:
        reasons.append("projected_ownership_invalid")

    unique_reasons = tuple(dict.fromkeys(reasons))
    return FreshnessAssessment(ready=not unique_reasons, reasons=unique_reasons, metrics=metrics)
