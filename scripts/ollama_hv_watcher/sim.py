"""Total-draft-value simulation for the Ollama HV helper (#620).

The sport apps publish the freeze. This module scores a five-player card
under the same committed-order law those apps optimize:

    value * (slot_multiplier + card_boost)

with slots (2.0, 1.8, 1.6, 1.4, 1.2). Notes stay annotations. The sim is
the machine-readable objective on each learn tick.

NHL boosts stay 0 here. This helper cannot see whether every club has a
game played, so it does not arm a boost the serve gate would still zero.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import combinations
from typing import Any

SLOT_MULTIPLIERS: tuple[float, float, float, float, float] = (2.0, 1.8, 1.6, 1.4, 1.2)
FIVE = 5
# Combinations of the prefiltered pool. Boards larger than this are cut to
# the best `value * (top slot + boost)` candidates before the exact search.
_ENUM_CAP = 16


def card_boost(row: Mapping[str, Any], *, sport: str) -> float:
    """Boost that enters the sim. NHL is forced to 0."""

    if sport.lower() == "nhl":
        return 0.0
    raw = row.get("card_boost")
    if raw is None:
        return 0.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if value < 0.0:
        return 0.0
    return value


def _value(row: Mapping[str, Any]) -> float | None:
    raw = row.get("value")
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value


def committed_total_value(
    lineup: Sequence[Mapping[str, Any]],
    *,
    sport: str,
) -> float:
    """Score ``lineup`` in its current slot order. Missing values count as 0."""

    total = 0.0
    for slot, row in zip(SLOT_MULTIPLIERS, lineup, strict=False):
        value = _value(row)
        if value is None:
            continue
        total += value * (slot + card_boost(row, sport=sport))
    return total


def _optimal_order(
    players: Sequence[Mapping[str, Any]],
    *,
    sport: str,
) -> tuple[Mapping[str, Any], ...]:
    """Largest raw value takes the largest slot. Boost does not reorder slots.

    ``value * (slot + boost) = value * slot + value * boost``. The boost term
    depends only on membership. The slot term is maximized by pairing the
    largest value with the largest multiplier.
    """

    return tuple(
        sorted(
            players,
            key=lambda row: (
                -(_value(row) or float("-inf")),
                str(row.get("player_id") or ""),
            ),
        )
    )


def _set_score(players: Sequence[Mapping[str, Any]], *, sport: str) -> float:
    ordered = _optimal_order(players, sport=sport)
    return committed_total_value(ordered, sport=sport)


def total_value_lineup(
    players: Sequence[Mapping[str, Any]],
    *,
    sport: str,
) -> tuple[dict[str, Any], ...]:
    """Pick and slot the five that maximize committed total value.

    Raises ``ValueError`` when fewer than five distinct players have a value.
    """

    unique: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for row in players:
        if _value(row) is None:
            continue
        key = str(row.get("player_id") or row.get("name") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(row)
    if len(unique) < FIVE:
        raise ValueError(
            f"need_five_players_every_day:sim_pool={len(unique)} need={FIVE}"
        )
    pool = unique
    if len(pool) > _ENUM_CAP:
        pool = sorted(
            pool,
            key=lambda row: (
                -(
                    (_value(row) or 0.0)
                    * (SLOT_MULTIPLIERS[0] + card_boost(row, sport=sport))
                )
            ),
        )[:_ENUM_CAP]
    best_score = float("-inf")
    best: tuple[Mapping[str, Any], ...] = ()
    for combo in combinations(pool, FIVE):
        score = _set_score(combo, sport=sport)
        ordered_ids = tuple(sorted(str(row.get("player_id") or "") for row in combo))
        best_ids = tuple(sorted(str(row.get("player_id") or "") for row in best))
        if score > best_score or (
            score == best_score and (not best or ordered_ids < best_ids)
        ):
            best_score = score
            best = _optimal_order(combo, sport=sport)
    return _as_card(best, sport=sport)


def _as_card(
    ordered: Sequence[Mapping[str, Any]],
    *,
    sport: str,
) -> tuple[dict[str, Any], ...]:
    out: list[dict[str, Any]] = []
    for index, row in enumerate(ordered, start=1):
        card_row: dict[str, Any] = {
            "slot": index,
            "player_id": row.get("player_id"),
            "name": row.get("name"),
            "team": row.get("team"),
            "value": row.get("value"),
        }
        boost = card_boost(row, sport=sport)
        if sport.lower() != "nhl" and row.get("card_boost") is not None:
            card_row["card_boost"] = boost
        if sport.lower() == "nhl":
            card_row["card_boost"] = 0.0
        out.append(card_row)
    return tuple(out)


def sim_report(
    lineup: Sequence[Mapping[str, Any]],
    *,
    sport: str,
    selection: str,
) -> dict[str, Any]:
    """Machine block stored on a learn tick. Does not publish a lineup."""

    return {
        "objective": "total_draft_value",
        "law": "value * (slot_multiplier + card_boost)",
        "slot_multipliers": list(SLOT_MULTIPLIERS),
        "lineup_total_value": committed_total_value(lineup, sport=sport),
        "selection": selection,
        "nhl_boost": "forced_zero" if sport.lower() == "nhl" else "row_card_boost",
        "publishes_lineup": False,
        "role": "model_sim",
    }
