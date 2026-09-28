"""Optional Ollama slate-shape influence for WNBA freeze scores (#574).

Default OFF. When ``WNBA_OLLAMA_INFLUENCE`` is truthy, load ``advice.json``
from ``WNBA_OLLAMA_ADVICE_PATH`` and multiply optimizer scores by bounded
per-player mults. Missing, stale, wrong-slate, or malformed advice is
identity. This module does not open the network. Classic job2 scoring is
unchanged when the flag is unset.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from oracle_core.slate_advice import advice_is_fresh, tilt_map_from_payload

INFLUENCE_ENV = "WNBA_OLLAMA_INFLUENCE"
ADVICE_PATH_ENV = "WNBA_OLLAMA_ADVICE_PATH"


def influence_enabled(environ: Mapping[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    return (env.get(INFLUENCE_ENV) or "").strip().lower() in {"1", "true", "yes", "on"}


def _load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def load_tilt_map(
    *,
    slate_id: str,
    sport: str = "wnba",
    environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> dict[int, float]:
    if not influence_enabled(environ):
        return {}
    env = environ if environ is not None else os.environ
    path_raw = (env.get(ADVICE_PATH_ENV) or "").strip()
    if not path_raw:
        return {}
    payload = _load_json_file(Path(path_raw))
    if payload is None:
        return {}
    clock = now if now is not None else datetime.now(UTC)
    if not advice_is_fresh(payload, sport=sport, slate_id=slate_id, now=clock):
        return {}
    return tilt_map_from_payload(payload)


def apply_ollama_influence(
    scores: Mapping[int, float],
    *,
    tilts: Mapping[int, float],
) -> dict[int, float]:
    if not tilts:
        return dict(scores)
    return {pid: float(score) * float(tilts.get(pid, 1.0)) for pid, score in scores.items()}
