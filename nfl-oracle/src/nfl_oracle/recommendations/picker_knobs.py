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
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
import math
from statistics import mean, pstdev

from pydantic import Field, field_validator

from nfl_oracle.recommendations.model import Projection
from nfl_oracle.recommendations.schema import Record, Slate


class PickerKnobs(Record):
    """Post-predict projection adjustments. Identity when every weight is 0."""

    boost_rank_blend: float = Field(default=0.0, ge=0.0, le=1.0)
    position_calibration: float = Field(default=0.0, ge=0.0, le=1.0)
    profile: str = "identity"

    @field_validator("profile")
    @classmethod
    def _profile_token(cls, value: str) -> str:
        token = value.strip() or "identity"
        cleaned = token.replace("_", "").replace("-", "").replace(".", "")
        if not cleaned.isalnum():
            raise ValueError("picker_profile_invalid")
        return token


def picker_knobs_from_env(environ: Mapping[str, str] | None = None) -> PickerKnobs:
    """Read ``NFL_PICKER_BOOST_RANK_BLEND`` / ``NFL_PICKER_POSITION_CALIBRATION``.

    Missing or empty values keep the identity defaults. Invalid floats raise
    ``ValueError`` so a mis-set Railway knob fails closed rather than silently
    ignoring the override.
    """
    env = environ if environ is not None else os.environ
    blend = _env_unit_float(env, "NFL_PICKER_BOOST_RANK_BLEND", 0.0)
    position = _env_unit_float(env, "NFL_PICKER_POSITION_CALIBRATION", 0.0)
    profile = (env.get("NFL_PICKER_PROFILE") or "identity").strip() or "identity"
    if blend == 0.0 and position == 0.0:
        profile = "identity"
    elif profile == "identity" and (blend > 0.0 or position > 0.0):
        profile = "env"
    return PickerKnobs(
        boost_rank_blend=blend,
        position_calibration=position,
        profile=profile,
    )


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
    """
    if knobs.boost_rank_blend == 0.0 and knobs.position_calibration == 0.0:
        return tuple(projections)
    boost_of = {c.player_id: float(c.card_boost) for c in slate.candidates}
    position_of = {c.player_id: c.position for c in slate.candidates}
    by_id = {p.player_id: p for p in projections}
    if set(by_id) != {c.player_id for c in slate.candidates}:
        raise ValueError("projection_slate_player_mismatch")

    aligned = _boost_aligned_means(projections, boost_of)
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
                    "stddev": _stddev_with_availability(new_samples, probability, sample_center),
                }
            )
        )
    return tuple(adjusted)


def _boost_aligned_means(
    projections: Sequence[Projection],
    boost_of: Mapping[int, float],
) -> dict[int, float]:
    """Reassign projected conditional means in ascending boost order.

    Ties in boost break by player_id so the map is deterministic. The multiset
    of values is preserved; only the assignment to players changes. When every
    boost in the pool is equal (zero-boost or uniform-boost regime), return the
    original conditional means unchanged so player_id tie-breaks cannot shuffle
    projections.
    """
    boost_values = {float(boost_of[p.player_id]) for p in projections}
    if len(boost_values) <= 1:
        return {p.player_id: p.conditional_mean for p in projections}
    ordered_values = sorted(p.conditional_mean for p in projections)
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
    result: float = (
        probability * conditional_variance + probability * (1.0 - probability) * conditional**2
    ) ** 0.5
    return result


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
        f"{knobs.profile}:boost={knobs.boost_rank_blend:.2f},pos={knobs.position_calibration:.2f}"
    )
