"""Domain-free slate advice document (#574).

Sport apps may multiply projections by ``tilts`` when their own env flag is
on. This module does not read the process environment and does not open the
network. Missing, stale, wrong-slate, or malformed advice is an empty map.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

MULT_MIN = 0.85
MULT_MAX = 1.15
DEFAULT_MAX_AGE_SECONDS = 3 * 60 * 60


def clamp_mult(value: float) -> float:
    return max(MULT_MIN, min(MULT_MAX, float(value)))


def parse_iso_utc(value: str) -> datetime:
    text = str(value).strip().replace("Z", "+00:00")
    return datetime.fromisoformat(text).astimezone(UTC)


def advice_is_fresh(
    payload: dict[str, Any],
    *,
    sport: str,
    slate_id: str,
    now: datetime,
) -> bool:
    if str(payload.get("sport") or "").lower() != sport.lower():
        return False
    if str(payload.get("slate_id") or "") != str(slate_id):
        return False
    written_raw = payload.get("written_at")
    if not written_raw:
        return False
    try:
        written = parse_iso_utc(str(written_raw))
        max_age = int(payload.get("max_age_seconds") or DEFAULT_MAX_AGE_SECONDS)
    except (TypeError, ValueError):
        return False
    age = (now - written).total_seconds()
    return 0.0 <= age <= float(max_age)


def tilt_map_from_payload(payload: dict[str, Any]) -> dict[int, float]:
    rows = payload.get("tilts")
    if not isinstance(rows, list):
        return {}
    out: dict[int, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = row.get("player_id")
        if pid is None:
            continue
        try:
            player_id = int(pid)
            mult = clamp_mult(float(row.get("mult", 1.0)))
        except (TypeError, ValueError):
            continue
        if abs(mult - 1.0) < 1e-9:
            continue
        out[player_id] = mult
    return out
