"""Enumerate ordered five-card actions for offline shadow comparisons.

Produces the 5! = 120 orderings of a distinct five-player set. This is a
combinatorial helper for research only — not provider inventory, eligibility,
or contest submission.
"""

from __future__ import annotations

from itertools import permutations

from nfl_oracle.strategy.schema import FiveCardAction, check_action

ORDERINGS_PER_SET = 120


def ordered_five_card_actions(
    player_ids: tuple[int, int, int, int, int] | list[int],
    *,
    slot_multipliers: tuple[float, float, float, float, float] | None = None,
) -> tuple[FiveCardAction, ...]:
    """Return all distinct orderings as FiveCardAction values.

    Raises ValueError if the input set is not exactly five positive distinct ids.
    """

    ids = tuple(int(p) for p in player_ids)
    probe = FiveCardAction(player_ids=ids, slot_multipliers=slot_multipliers)  # type: ignore[arg-type]
    legality = check_action(probe)
    if not legality.structurally_valid:
        raise ValueError(",".join(legality.structural_errors) or "invalid_five_card_set")

    actions: list[FiveCardAction] = []
    for ordered in permutations(ids, 5):
        actions.append(
            FiveCardAction(
                player_ids=(ordered[0], ordered[1], ordered[2], ordered[3], ordered[4]),
                slot_multipliers=slot_multipliers,
            )
        )
    if len(actions) != ORDERINGS_PER_SET:
        raise RuntimeError(f"expected_{ORDERINGS_PER_SET}_orderings_got_{len(actions)}")
    return tuple(actions)


def best_shadow_ordering(
    player_ids: tuple[int, int, int, int, int] | list[int],
    values_by_player: dict[int, float],
    *,
    slot_multipliers: tuple[float, float, float, float, float] | None = None,
    default_multiplier: float = 1.0,
) -> tuple[FiveCardAction, float]:
    """Pick the ordering maximizing observation-only weighted shadow score."""

    from nfl_oracle.strategy.scoring import shadow_weighted_score

    best_action: FiveCardAction | None = None
    best_total = float("-inf")
    for action in ordered_five_card_actions(player_ids, slot_multipliers=slot_multipliers):
        score = shadow_weighted_score(
            action,
            values_by_player,
            default_multiplier=default_multiplier,
        )
        if score.total > best_total:
            best_total = score.total
            best_action = action
    assert best_action is not None
    return best_action, best_total
