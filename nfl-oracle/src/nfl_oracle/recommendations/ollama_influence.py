"""Optional Ollama slate-shape influence for NFL projections (#574).

Default OFF. When ``NFL_OLLAMA_INFLUENCE`` is truthy, load advice from
``NFL_OLLAMA_ADVICE_PATH`` (file) or ``NFL_OLLAMA_ADVICE_URL`` (HTTP) and
multiply conditional means / samples by bounded per-player mults. Missing,
stale, wrong-slate, or malformed advice is ignored (identity).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from nfl_oracle.recommendations.model import Projection

INFLUENCE_ENV = "NFL_OLLAMA_INFLUENCE"
ADVICE_PATH_ENV = "NFL_OLLAMA_ADVICE_PATH"
ADVICE_URL_ENV = "NFL_OLLAMA_ADVICE_URL"
DEFAULT_MAX_AGE_SECONDS = 3 * 60 * 60
MULT_MIN = 0.85
MULT_MAX = 1.15
HTTP_TIMEOUT_S = 5.0
USER_AGENT = "nfl-oracle-ollama-influence/1 (+#574)"


def influence_enabled(environ: Mapping[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    return (env.get(INFLUENCE_ENV) or "").strip().lower() in {"1", "true", "yes", "on"}


def _clamp(mult: float) -> float:
    return max(MULT_MIN, min(MULT_MAX, float(mult)))


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).astimezone(UTC)


def _fresh(payload: dict[str, Any], *, sport: str, slate_id: str, now: datetime) -> bool:
    if str(payload.get("sport") or "").lower() != sport.lower():
        return False
    if str(payload.get("slate_id") or "") != str(slate_id):
        return False
    written_raw = payload.get("written_at")
    if not written_raw:
        return False
    try:
        written = _parse_iso(str(written_raw))
        max_age = int(payload.get("max_age_seconds") or DEFAULT_MAX_AGE_SECONDS)
    except (TypeError, ValueError):
        return False
    age = (now - written).total_seconds()
    return 0.0 <= age <= float(max_age)


def _tilt_map(payload: dict[str, Any]) -> dict[int, float]:
    rows = payload.get("tilts")
    if not isinstance(rows, list):
        return {}
    out: dict[int, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            pid = int(row["player_id"])
            mult = _clamp(float(row.get("mult", 1.0)))
        except (KeyError, TypeError, ValueError):
            continue
        if abs(mult - 1.0) < 1e-9:
            continue
        out[pid] = mult
    return out


def _load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_json_url(url: str) -> dict[str, Any] | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
            body = response.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def load_tilt_map(
    *,
    slate_id: str,
    sport: str = "nfl",
    environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> dict[int, float]:
    """Return player_id→mult when influence is on and advice is fresh; else {}."""

    if not influence_enabled(environ):
        return {}
    env = environ if environ is not None else os.environ
    clock = now if now is not None else datetime.now(UTC)
    payload: dict[str, Any] | None = None
    path_raw = (env.get(ADVICE_PATH_ENV) or "").strip()
    if path_raw:
        payload = _load_json_file(Path(path_raw))
    if payload is None:
        url = (env.get(ADVICE_URL_ENV) or "").strip()
        if url:
            payload = _load_json_url(url)
    if payload is None or not _fresh(payload, sport=sport, slate_id=slate_id, now=clock):
        return {}
    return _tilt_map(payload)


def apply_ollama_influence(
    projections: Sequence[Projection],
    *,
    tilts: Mapping[int, float],
) -> tuple[Projection, ...]:
    """Multiply conditional means/samples by tilt mults; identity when empty."""

    if not tilts:
        return tuple(projections)
    adjusted: list[Projection] = []
    for projection in projections:
        mult = float(tilts.get(projection.player_id, 1.0))
        if abs(mult - 1.0) < 1e-9:
            adjusted.append(projection)
            continue
        new_cond = projection.conditional_mean * mult
        new_samples = tuple(sample * mult for sample in projection.samples)
        sample_center = mean(new_samples) if new_samples else new_cond
        probability = projection.availability_probability
        new_mean = sample_center * probability
        adjusted.append(
            projection.model_copy(
                update={
                    "conditional_mean": new_cond,
                    "mean": new_mean,
                    "samples": new_samples,
                    "provenance": projection.provenance + (f"ollama_influence:mult={mult:.4f}",),
                }
            )
        )
    return tuple(adjusted)
