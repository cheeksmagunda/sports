"""Evidence-backed projection knobs applied after predict, before optimize (#280).

Production scoring already uses ``value * (slot + boost)``. These knobs adjust
the *projected value* itself when the provider's card boost (assigned from the
pre-game Real ranking) and/or per-position holdout residuals carry signal the
ridge projection is under-using. Defaults are identity: no change unless an
explicit blend weight is set (env or call site).

Sunday risk: changing these knobs changes which five cards freeze. Measure
via ``nfl-contest-pool-replay`` / ``sweep_picker_knobs`` before live flips.
Standing authorization for evidence-backed live knob/Railway flips: commit
``3ec2bad`` ("per explicit operator authorization"), issue #37 implementation
authority, reaffirmed 2026-09-25 for NFL picker knobs. Record numbers in
STATUS.md when applying.

Optional Ollama tick tilt (#574): default weight 0 never opens a tick file.
Arm only with an explicit path + weight after mounting Codespace ticks.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import mean, pstdev
from typing import Literal

from pydantic import Field, field_validator

from nfl_oracle.recommendations.model import Projection
from nfl_oracle.recommendations.schema import Record, Slate


class PickerKnobs(Record):
    """Post-predict projection adjustments. Identity when every weight is 0."""

    boost_rank_blend: float = Field(default=0.0, ge=0.0, le=1.0)
    position_calibration: float = Field(default=0.0, ge=0.0, le=1.0)
    # Ollama tick tilt (#574): default off. Path required only when weight > 0.
    ollama_tick_tilt_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    ollama_tick_tilt_path: str = ""
    profile: str = "identity"
    # Inside one boost tier, assign higher aligned means to higher own
    # projections. ``player_id`` restores the previous tie-break.
    boost_tie_break: Literal["projection", "player_id"] = "projection"

    @field_validator("profile")
    @classmethod
    def _profile_token(cls, value: str) -> str:
        token = value.strip() or "identity"
        cleaned = token.replace("_", "").replace("-", "").replace(".", "")
        if not cleaned.isalnum():
            raise ValueError("picker_profile_invalid")
        return token


def picker_knobs_from_env(environ: Mapping[str, str] | None = None) -> PickerKnobs:
    """Read picker env knobs including optional Ollama tick tilt (#574).

    ``NFL_PICKER_BOOST_RANK_BLEND`` and ``NFL_PICKER_POSITION_CALIBRATION``
    missing or empty keep the identity defaults. ``NFL_PICKER_BOOST_TIEBREAK``
    defaults to ``projection`` (own conditional mean inside a boost tier);
    ``player_id`` restores the previous tie-break. Invalid values raise
    ``ValueError`` so a mis-set Railway knob fails closed rather than silently
    ignoring the override. ``NFL_OLLAMA_TICK_TILT_WEIGHT`` default 0 never
    opens a tick file (today's freeze unchanged unless explicitly armed).
    """
    from nfl_oracle.recommendations.ollama_tick_tilt import ollama_tilt_from_env

    env = environ if environ is not None else os.environ
    blend = _env_unit_float(env, "NFL_PICKER_BOOST_RANK_BLEND", 0.0)
    position = _env_unit_float(env, "NFL_PICKER_POSITION_CALIBRATION", 0.0)
    ollama_weight, ollama_path = ollama_tilt_from_env(env)
    profile = (env.get("NFL_PICKER_PROFILE") or "identity").strip() or "identity"
    active = blend > 0.0 or position > 0.0 or ollama_weight > 0.0
    if not active:
        profile = "identity"
    elif profile == "identity":
        profile = "env"
    return PickerKnobs(
        boost_rank_blend=blend,
        position_calibration=position,
        ollama_tick_tilt_weight=ollama_weight,
        ollama_tick_tilt_path=str(ollama_path) if ollama_path is not None else "",
        profile=profile,
        boost_tie_break=_env_boost_tie_break(env),
    )


def _env_boost_tie_break(env: Mapping[str, str]) -> Literal["projection", "player_id"]:
    raw = (env.get("NFL_PICKER_BOOST_TIEBREAK") or "").strip().lower()
    if not raw or raw == "projection":
        return "projection"
    if raw == "player_id":
        return "player_id"
    raise ValueError("NFL_PICKER_BOOST_TIEBREAK_invalid")


def _env_unit_float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = (env.get(key) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError(f"{key}_invalid") from error
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{key}_out_of_range")
    return value


def position_residual_bias(
    residuals_by_position: Mapping[str, Sequence[float]],
) -> dict[str, float]:
    """Mean (actual - predicted) residual per position; empty inputs omitted."""
    out: dict[str, float] = {}
    for position, residuals in residuals_by_position.items():
        if residuals:
            out[position] = mean(residuals)
    return out


def apply_picker_knobs(
    projections: Sequence[Projection],
    slate: Slate,
    *,
    knobs: PickerKnobs,
    position_bias: Mapping[str, float] | None = None,
) -> tuple[Projection, ...]:
    """Return projections adjusted by ``knobs``; identity when weights are 0.

    Boost-rank blend: within the slate, build a boost-aligned value table that
    keeps the same multiset of projected means but reassigns them in boost
    order (provider ranking signal). Blend that table into each player's mean,
    conditional_mean, and residual samples.

    Position calibration: add ``position_calibration * bias[position]`` to the
    conditional mean (and samples), where bias is mean holdout residual
    (actual - predicted) for that position. Missing positions get 0.

    Ollama tick tilt (#574): when ``ollama_tick_tilt_weight`` > 0, multiply
    means for the tick's five by a slot-weighted factor. Default weight 0
    never opens the path (satellite / identity on live freeze).
    """
    from nfl_oracle.recommendations.ollama_tick_tilt import (
        apply_ollama_tick_tilt,
        load_slot_multipliers,
    )

    identity = (
        knobs.boost_rank_blend == 0.0
        and knobs.position_calibration == 0.0
        and knobs.ollama_tick_tilt_weight == 0.0
    )
    if identity:
        return tuple(projections)
    boost_of = {c.player_id: float(c.card_boost) for c in slate.candidates}
    position_of = {c.player_id: c.position for c in slate.candidates}
    by_id = {p.player_id: p for p in projections}
    if set(by_id) != {c.player_id for c in slate.candidates}:
        raise ValueError("projection_slate_player_mismatch")

    if knobs.boost_rank_blend == 0.0 and knobs.position_calibration == 0.0:
        adjusted_tuple: tuple[Projection, ...] = tuple(projections)
    else:
        aligned = _boost_aligned_means(
            projections, boost_of, tie_break=knobs.boost_tie_break
        )
        bias = position_bias or {}
        adjusted: list[Projection] = []
        for projection in projections:
            player_id = projection.player_id
            base_cond = projection.conditional_mean
            target = aligned[player_id]
            blended = (1.0 - knobs.boost_rank_blend) * base_cond + knobs.boost_rank_blend * target
            pos_bias = float(bias.get(position_of[player_id], 0.0))
            calibrated = blended + knobs.position_calibration * pos_bias
            delta = calibrated - base_cond
            probability = projection.availability_probability
            new_samples = tuple(sample + delta for sample in projection.samples)
            sample_center = mean(new_samples) if new_samples else calibrated
            # Keep mean = conditional * availability, matching predict().
            new_mean = sample_center * probability
            provenance = projection.provenance + (
                f"picker:{knobs.profile}",
                f"boost_rank_blend={knobs.boost_rank_blend:.3f}",
                f"position_calibration={knobs.position_calibration:.3f}",
            )
            adjusted.append(
                projection.model_copy(
                    update={
                        "conditional_mean": calibrated,
                        "mean": new_mean,
                        "samples": new_samples,
                        "provenance": provenance,
                        "stddev": _stddev_with_availability(
                            new_samples, probability, sample_center
                        ),
                    }
                )
            )
        adjusted_tuple = tuple(adjusted)
    if knobs.ollama_tick_tilt_weight == 0.0:
        return adjusted_tuple
    if not knobs.ollama_tick_tilt_path.strip():
        raise ValueError("ollama_tick_tilt_path_required")
    multipliers = load_slot_multipliers(
        Path(knobs.ollama_tick_tilt_path),
        weight=knobs.ollama_tick_tilt_weight,
    )
    return apply_ollama_tick_tilt(adjusted_tuple, multipliers=multipliers)


def _boost_aligned_means(
    projections: Sequence[Projection],
    boost_of: Mapping[int, float],
    *,
    tie_break: Literal["projection", "player_id"] = "projection",
) -> dict[int, float]:
    """Reassign projected conditional means in ascending boost order.

    The multiset of values is preserved; only the assignment to players
    changes. Inside one boost tier, ``projection`` gives the higher own
    conditional mean the higher aligned value. ``player_id`` is the previous
    tie-break and stays the last key when own projections also tie, so the
    map stays deterministic. When every boost in the pool is equal (zero-boost
    or uniform-boost regime), return the original conditional means unchanged.
    """
    if tie_break not in {"projection", "player_id"}:
        raise ValueError("boost_tie_break_invalid")
    boost_values = {float(boost_of[p.player_id]) for p in projections}
    if len(boost_values) <= 1:
        return {p.player_id: p.conditional_mean for p in projections}
    ordered_values = sorted(p.conditional_mean for p in projections)
    if tie_break == "projection":
        by_boost = sorted(
            projections,
            key=lambda p: (boost_of[p.player_id], p.conditional_mean, p.player_id),
        )
    else:
        by_boost = sorted(projections, key=lambda p: (boost_of[p.player_id], p.player_id))
    return {
        projection.player_id: value
        for projection, value in zip(by_boost, ordered_values, strict=True)
    }


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


def accumulate_position_residuals(
    *,
    position: str,
    residual: float,
    bucket: dict[str, list[float]],
) -> None:
    """Helper for fit_model holdout loops to collect per-position residuals."""
    bucket.setdefault(position, []).append(residual)


def summarize_knob_label(knobs: PickerKnobs) -> str:
    return (
        f"{knobs.profile}:boost={knobs.boost_rank_blend:.2f},"
        f"pos={knobs.position_calibration:.2f},"
        f"ollama={knobs.ollama_tick_tilt_weight:.2f}"
    )
