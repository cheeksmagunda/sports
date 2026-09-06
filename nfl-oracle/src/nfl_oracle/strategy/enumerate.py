"""Enumerate ordered five-card actions for offline shadow comparisons.

Produces the 5! = 120 orderings of a distinct five-player set. This is a
combinatorial helper for research only — not provider inventory, eligibility,
or contest submission.
"""

from __future__ import annotations

from itertools import permutations
from typing import Any

from nfl_oracle.strategy.algebra import (
    OBSERVED_DEFAULT_SLOT_MULTIPLIERS,
    contest_score_to_json,
    contest_shadow_score,
)
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
    boosts_by_player: dict[int, float] | None = None,
    default_multiplier: float = 1.0,
    use_contest_algebra: bool = False,
) -> tuple[FiveCardAction, float]:
    """Pick the ordering maximizing observation-only weighted shadow score.

    When ``use_contest_algebra`` is True, uses verified
    value * (slot + boost) scoring with observed default multipliers unless
    ``slot_multipliers`` is supplied. ``default_multiplier`` applies only to the
    legacy simple weighted sum path.
    """

    if use_contest_algebra:
        multis = slot_multipliers or OBSERVED_DEFAULT_SLOT_MULTIPLIERS
        best_action: FiveCardAction | None = None
        best_total = float("-inf")
        for action in ordered_five_card_actions(player_ids, slot_multipliers=multis):
            score = contest_shadow_score(
                action,
                values_by_player,
                boosts_by_player=boosts_by_player,
            )
            if not score.non_negative_branch:
                continue
            if score.total > best_total:
                best_total = score.total
                best_action = action
        if best_action is None:
            raise ValueError("no_valid_non_negative_ordering")
        return best_action, best_total

    from nfl_oracle.strategy.scoring import shadow_weighted_score

    best_action = None
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


def rank_shadow_orderings(
    player_ids: tuple[int, int, int, int, int] | list[int],
    values_by_player: dict[int, float],
    *,
    slot_multipliers: tuple[float, float, float, float, float] | None = None,
    boosts_by_player: dict[int, float] | None = None,
    top_k: int = 10,
    use_contest_algebra: bool = True,
) -> list[dict[str, Any]]:
    """Rank orderings by shadow score (research only; default contest algebra)."""

    multis = slot_multipliers
    if use_contest_algebra and multis is None:
        multis = OBSERVED_DEFAULT_SLOT_MULTIPLIERS

    ranked: list[tuple[float, FiveCardAction, dict[str, Any] | None]] = []
    for action in ordered_five_card_actions(player_ids, slot_multipliers=multis):
        if use_contest_algebra:
            score = contest_shadow_score(
                action,
                values_by_player,
                boosts_by_player=boosts_by_player,
            )
            if not score.non_negative_branch:
                continue
            ranked.append((score.total, action, contest_score_to_json(score)))
        else:
            from nfl_oracle.strategy.scoring import shadow_weighted_score

            simple = shadow_weighted_score(action, values_by_player)
            ranked.append(
                (
                    simple.total,
                    action,
                    {
                        "total": simple.total,
                        "per_slot": list(simple.per_slot),
                        "structural_ok": simple.structural_ok,
                        "notes": simple.notes,
                        "contest_entry": False,
                    },
                )
            )

    ranked.sort(key=lambda row: row[0], reverse=True)
    out: list[dict[str, Any]] = []
    for rank, (total, action, payload) in enumerate(ranked[: max(0, top_k)], start=1):
        out.append(
            {
                "rank": rank,
                "total": total,
                "player_ids": list(action.player_ids),
                "slot_multipliers": list(action.slot_multipliers)
                if action.slot_multipliers is not None
                else None,
                "score": payload,
                "contest_entry": False,
            }
        )
    return out
