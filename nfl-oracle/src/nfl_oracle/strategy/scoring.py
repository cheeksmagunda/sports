"""Shadow score helpers for ordered five-card actions.

Uses caller-supplied slot multipliers and player values. Does **not** call Real
Sports or submit entries. Provider scoring algebra remains #91-open; this is a
transparent weighted sum scaffold for offline comparisons only.
"""

from __future__ import annotations

from dataclasses import dataclass

from nfl_oracle.strategy.schema import FiveCardAction, check_action


@dataclass(frozen=True)
class ShadowScore:
    total: float
    per_slot: tuple[float, float, float, float, float]
    structural_ok: bool
    notes: str = "observation_only_weighted_sum"


def shadow_weighted_score(
    action: FiveCardAction,
    values_by_player: dict[int, float],
    *,
    default_multiplier: float = 1.0,
) -> ShadowScore:
    """Sum multiplier_i * value_i for each ordered slot (missing value -> 0)."""

    legality = check_action(action)
    multis = action.slot_multipliers or (default_multiplier,) * 5
    per: list[float] = []
    for pid, mult in zip(action.player_ids, multis, strict=True):
        per.append(float(mult) * float(values_by_player.get(pid, 0.0)))
    total = sum(per)
    note = "observation_only_weighted_sum"
    if not legality.structurally_valid:
        note = "structural_invalid;" + ",".join(legality.structural_errors)
    return ShadowScore(
        total=total,
        per_slot=(per[0], per[1], per[2], per[3], per[4]),
        structural_ok=legality.structurally_valid,
        notes=str(note),
    )
