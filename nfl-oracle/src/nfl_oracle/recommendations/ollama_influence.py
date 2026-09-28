"""Optional Ollama slate-shape influence for NFL projections (#574).

Default OFF. When ``NFL_OLLAMA_INFLUENCE`` is truthy, load ``advice.json``
from ``NFL_OLLAMA_ADVICE_PATH`` and multiply conditional means by bounded
per-player mults. Missing, stale, wrong-slate, or malformed advice is
identity. This module does not open the network. It does not read
``NFL_PICKER_BOOST_RANK_BLEND``; classic freeze stays on the picker path.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from oracle_core.slate_advice import advice_is_fresh, tilt_map_from_payload

from nfl_oracle.recommendations.model import Projection

INFLUENCE_ENV = "NFL_OLLAMA_INFLUENCE"
ADVICE_PATH_ENV = "NFL_OLLAMA_ADVICE_PATH"


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
    sport: str = "nfl",
    environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> dict[int, float]:
    """Return player_id to mult when influence is on and advice is fresh."""

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
    projections: Sequence[Projection],
    *,
    tilts: Mapping[int, float],
) -> tuple[Projection, ...]:
    """Multiply conditional means and samples. Empty tilts are identity."""

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
        adjusted.append(
            projection.model_copy(
                update={
                    "conditional_mean": new_cond,
                    "mean": sample_center * probability,
                    "samples": new_samples,
                    "provenance": projection.provenance + (f"ollama_influence:mult={mult:.4f}",),
                }
            )
        )
    return tuple(adjusted)
