"""Env-gated Ollama tick tilt for NFL picker projections (#574).

Codespace Ollama writes ``tick_*.json`` / ``latest_tick.json`` under
``data/ollama_hv/``. Those artifacts are **not** on the Railway worker volume
by default, so production freeze stays identity unless an operator mounts a
tick and sets a positive weight.

Contract (JSON): ``five_player_lineup`` list of objects with ``slot`` (1..5)
and ``player_id``. Weight 0 (default) never opens the file.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from nfl_oracle.recommendations.model import Projection

FIVE = 5
PATH_ENV = "NFL_OLLAMA_TICK_TILT_PATH"
WEIGHT_ENV = "NFL_OLLAMA_TICK_TILT_WEIGHT"


def ollama_tilt_from_env(
    environ: Mapping[str, str] | None = None,
) -> tuple[float, Path | None]:
    """Return ``(weight, path)``. Weight 0 → path ignored (identity)."""
    env = environ if environ is not None else os.environ
    raw_weight = (env.get(WEIGHT_ENV) or "").strip()
    if not raw_weight:
        weight = 0.0
    else:
        try:
            weight = float(raw_weight)
        except ValueError as error:
            raise ValueError(f"{WEIGHT_ENV}_invalid") from error
        if not 0.0 <= weight <= 1.0:
            raise ValueError(f"{WEIGHT_ENV}_out_of_range")
    if weight == 0.0:
        return 0.0, None
    raw_path = (env.get(PATH_ENV) or "").strip()
    if not raw_path:
        raise ValueError(f"{PATH_ENV}_required_when_weight_positive")
    return weight, Path(raw_path)


def resolve_tick_path(path: Path) -> Path:
    """Accept a tick file or a directory that contains ``latest_tick.json``."""
    path = Path(path)
    if path.is_dir():
        candidate = path / "latest_tick.json"
        if not candidate.is_file():
            raise ValueError("ollama_tick_latest_missing")
        return candidate
    if not path.is_file():
        raise ValueError("ollama_tick_path_missing")
    return path


def slot_multipliers_from_tick(
    payload: Mapping[str, Any],
    *,
    weight: float,
) -> dict[int, float]:
    """Map player_id → multiplicative tilt from ordered five-player card.

    Slot 1 gets ``1 + weight``; slot 5 gets ``1 + weight / 5``. Players absent
    from the tick (or with unusable ids) are omitted (implicit 1.0).
    """
    if weight == 0.0:
        return {}
    if not 0.0 < weight <= 1.0:
        raise ValueError("ollama_tick_tilt_weight_out_of_range")
    rows = payload.get("five_player_lineup")
    if not isinstance(rows, list) or len(rows) != FIVE:
        raise ValueError("ollama_tick_five_player_lineup_required")
    out: dict[int, float] = {}
    seen_slots: set[int] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("ollama_tick_lineup_row_invalid")
        try:
            slot = int(row["slot"])
            player_id = int(row["player_id"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("ollama_tick_lineup_slot_or_player_id_invalid") from error
        if slot < 1 or slot > FIVE:
            raise ValueError("ollama_tick_slot_out_of_range")
        if slot in seen_slots:
            raise ValueError("ollama_tick_duplicate_slot")
        if player_id in out:
            raise ValueError("ollama_tick_duplicate_player")
        seen_slots.add(slot)
        fraction = (FIVE + 1 - slot) / FIVE
        out[player_id] = 1.0 + weight * fraction
    if len(seen_slots) != FIVE:
        raise ValueError("ollama_tick_slots_incomplete")
    return out


def load_slot_multipliers(path: Path, *, weight: float) -> dict[int, float]:
    tick_path = resolve_tick_path(path)
    payload = json.loads(tick_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("ollama_tick_payload_not_object")
    return slot_multipliers_from_tick(payload, weight=weight)


def apply_ollama_tick_tilt(
    projections: Sequence[Projection],
    *,
    multipliers: Mapping[int, float],
) -> tuple[Projection, ...]:
    """Scale conditional means / samples for players present in ``multipliers``."""
    if not multipliers:
        return tuple(projections)
    adjusted: list[Projection] = []
    for projection in projections:
        factor = float(multipliers.get(projection.player_id, 1.0))
        if factor == 1.0:
            adjusted.append(projection)
            continue
        probability = projection.availability_probability
        new_conditional = projection.conditional_mean * factor
        new_samples = tuple(sample * factor for sample in projection.samples)
        sample_center = mean(new_samples) if new_samples else new_conditional
        new_mean = sample_center * probability
        adjusted.append(
            projection.model_copy(
                update={
                    "conditional_mean": new_conditional,
                    "mean": new_mean,
                    "samples": new_samples,
                    "provenance": projection.provenance + (f"ollama_tick_tilt={factor:.4f}",),
                    "stddev": _stddev_with_availability(new_samples, probability, sample_center),
                }
            )
        )
    return tuple(adjusted)


def _stddev_with_availability(
    samples: Sequence[float], probability: float, conditional: float
) -> float:
    if len(samples) < 2:
        conditional_variance = 0.0
    else:
        conditional_variance = pstdev(samples) ** 2
    return math.sqrt(
        probability * conditional_variance + probability * (1.0 - probability) * conditional**2
    )
