"""Verified Real Sports NFL five-card scoring algebra (observation only).

Source: Drive strategy playbook, NFL empirical findings 2026-09-02 (contests
870 / 1069 / 1070). Non-negative branch verified exactly:

    slot_multiplier(order) = defaultMultipliers[order]  # 0-indexed
    multiplier             = slot_multiplier + multiplierBonus
    item_score             = value * multiplier
    entry.score            = sum(item_score)

``OBSERVED_DEFAULT_SLOT_MULTIPLIERS`` is the platform default seen on draftinfo;
callers should prefer per-contest ``defaultMultipliers`` when available.

Negative ``value`` handling is unresolved (non-NFL row observed where multiplier
did not amplify a negative). This module refuses the non-negative formula when
any value is negative unless ``allow_unresolved_negative=True``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nfl_oracle.strategy.schema import FiveCardAction, check_action

# Observed on NFL contest 1069 draftinfo (byte-identical on non-NFL 2124).
OBSERVED_DEFAULT_SLOT_MULTIPLIERS: tuple[float, float, float, float, float] = (
    2.0,
    1.8,
    1.6,
    1.4,
    1.2,
)

BOOST_RANGE_OBSERVED = (0.0, 3.0)
BOOST_STEP_OBSERVED = 0.1


@dataclass(frozen=True)
class ContestItemScore:
    player_id: int
    slot_index: int  # 0..4
    value: float
    slot_multiplier: float
    multiplier_bonus: float
    effective_multiplier: float
    score: float


@dataclass(frozen=True)
class ContestShadowScore:
    total: float
    per_slot: tuple[ContestItemScore, ...]
    structural_ok: bool
    non_negative_branch: bool
    notes: str
    contest_entry: bool = False


def scoring_document() -> dict[str, Any]:
    """Machine-readable scoring contract for research service / CLI."""

    return {
        "name": "nfl_contest_scoring_algebra",
        "version": 1,
        "contest_entry": False,
        "observation_only": True,
        "issue_refs": ["#89", "#91"],
        "verified_on": ["contest_870", "contest_1069", "contest_1070"],
        "formula": {
            "non_negative": (
                "item_score = value * (slot_multiplier + multiplierBonus); "
                "entry.score = sum(item_score)"
            ),
            "negative_value": "unresolved_do_not_apply_non_negative_formula",
        },
        "observed_default_slot_multipliers": list(OBSERVED_DEFAULT_SLOT_MULTIPLIERS),
        "boost": {
            "field": "multiplierBonus",
            "range": list(BOOST_RANGE_OBSERVED),
            "step": BOOST_STEP_OBSERVED,
            "pre_lock_visibility": "unobserved_search_showed_zeros",
        },
        "notes": [
            "Prefer per-contest draftinfo.defaultMultipliers over the observed default.",
            "baseBoostedValue = value * (1 + multiplierBonus) is a 1x reference, not attainable.",
            "Slot and boost are additive in the multiplier, not multiplicative.",
        ],
    }


def resolve_slot_multipliers(
    action: FiveCardAction,
    *,
    default: tuple[float, float, float, float, float] = OBSERVED_DEFAULT_SLOT_MULTIPLIERS,
) -> tuple[float, float, float, float, float]:
    if action.slot_multipliers is not None:
        return action.slot_multipliers
    return default


def contest_shadow_score(
    action: FiveCardAction,
    values_by_player: dict[int, float],
    *,
    boosts_by_player: dict[int, float] | None = None,
    allow_unresolved_negative: bool = False,
    default_slot_multipliers: tuple[
        float, float, float, float, float
    ] = OBSERVED_DEFAULT_SLOT_MULTIPLIERS,
) -> ContestShadowScore:
    """Observation-only score under the verified non-negative algebra."""

    legality = check_action(action)
    boosts = boosts_by_player or {}
    multis = resolve_slot_multipliers(action, default=default_slot_multipliers)
    items: list[ContestItemScore] = []
    any_negative = False
    for slot_index, (pid, slot_m) in enumerate(zip(action.player_ids, multis, strict=True)):
        value = float(values_by_player.get(pid, 0.0))
        if value < 0:
            any_negative = True
        bonus = float(boosts.get(pid, 0.0))
        effective = float(slot_m) + bonus
        score = value * effective
        items.append(
            ContestItemScore(
                player_id=pid,
                slot_index=slot_index,
                value=value,
                slot_multiplier=float(slot_m),
                multiplier_bonus=bonus,
                effective_multiplier=effective,
                score=score,
            )
        )

    if any_negative and not allow_unresolved_negative:
        return ContestShadowScore(
            total=0.0,
            per_slot=tuple(items),
            structural_ok=legality.structurally_valid,
            non_negative_branch=False,
            notes="negative_value_branch_unresolved;refused_non_negative_formula",
        )

    note = "verified_non_negative_algebra"
    if not legality.structurally_valid:
        note = "structural_invalid;" + ",".join(legality.structural_errors)
    elif any_negative:
        note = "unresolved_negative_applied_with_explicit_override"

    return ContestShadowScore(
        total=sum(i.score for i in items),
        per_slot=tuple(items),
        structural_ok=legality.structurally_valid,
        non_negative_branch=not any_negative,
        notes=note,
    )


def contest_score_to_json(score: ContestShadowScore) -> dict[str, Any]:
    return {
        "total": score.total,
        "structural_ok": score.structural_ok,
        "non_negative_branch": score.non_negative_branch,
        "notes": score.notes,
        "contest_entry": False,
        "per_slot": [
            {
                "player_id": item.player_id,
                "slot_index": item.slot_index,
                "value": item.value,
                "slot_multiplier": item.slot_multiplier,
                "multiplier_bonus": item.multiplier_bonus,
                "effective_multiplier": item.effective_multiplier,
                "score": item.score,
            }
            for item in score.per_slot
        ],
    }
