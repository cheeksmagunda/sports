"""Five-player daily contest pick contract for Ollama HV/TDV (#574).

Real Sports contests here are always an ordered five-player lineup.
Every slate day the watcher must propose exactly FIVE_PLAYER_LINEUP_SIZE
distinct players; never fewer, never more.

When the board is a sport app's frozen lineup (``section ==
APP_FROZEN_SECTION``) the helper uses ``frozen_app_lineup``: the app's five
in the app's slot order. The helper annotates; it never replaces.
"""

from __future__ import annotations

from typing import Any

from ollama_hv_watcher.boards import BoardSummary

# Hard contest size: five players every day, every sport.
FIVE_PLAYER_LINEUP_SIZE = 5
APP_FROZEN_SECTION = "app_frozen_lineup"

# Observed Real Sports default slot multipliers (slot 1..5).
OBSERVED_SLOT_MULTIPLIERS: tuple[float, float, float, float, float] = (
    2.0,
    1.8,
    1.6,
    1.4,
    1.2,
)

CHALK_VS_MULTIPLIER_PRINCIPLE = (
    "chalk_vs_multiplier: put true HV/TDV (max_value / top_1) into high "
    "multiplier slots even when chalk (high drafts); fade soft chalk that "
    "lacks HV; never chase ownership alone."
)
_CARD_EXTRA_KEYS = ("position", "opponent", "card_boost", "slot_multiplier")


def five_player_lineup(
    summary: BoardSummary,
    *,
    size: int = FIVE_PLAYER_LINEUP_SIZE,
) -> tuple[dict[str, Any], ...]:
    """Return the top ``size`` distinct ranked players as the daily pick.

    Raises ``ValueError`` when the board cannot fill a full five-player card.
    Pregame boards never emit ``real_score`` (leak stop).
    """
    if size != FIVE_PLAYER_LINEUP_SIZE:
        raise ValueError(f"lineup_size_must_be_{FIVE_PLAYER_LINEUP_SIZE}_got_{size}")
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in summary.top_players:
        key = str(row.get("player_id") or row.get("name") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        card_row: dict[str, Any] = {
            "slot": len(out) + 1,
            "player_id": row.get("player_id"),
            "name": row.get("name"),
            "team": row.get("team"),
            "value": row.get("value"),
        }
        if not summary.is_pregame:
            # Explicit history path only; pregame boards carry no outcomes.
            card_row["real_score"] = row.get("real_score")
        out.append(card_row)
        if len(out) >= FIVE_PLAYER_LINEUP_SIZE:
            break
    if len(out) < FIVE_PLAYER_LINEUP_SIZE:
        raise ValueError(
            "need_five_players_every_day:"
            f"board={summary.path or summary.slate_key or '?'} "
            f"have={len(out)} need={FIVE_PLAYER_LINEUP_SIZE}"
        )
    return tuple(out)


def frozen_app_lineup(summary: BoardSummary) -> tuple[dict[str, Any], ...]:
    """Return the sport app's own frozen five in the app's slot order.

    Fails closed unless the board is a pregame app-frozen board with exactly
    five players whose slots are 1..5.
    """

    if summary.section != APP_FROZEN_SECTION:
        raise ValueError(f"not_an_app_frozen_board:section={summary.section!r}")
    if not summary.is_pregame:
        raise ValueError("app_frozen_board_must_be_pregame")
    rows = list(summary.top_players)
    if summary.player_count != FIVE_PLAYER_LINEUP_SIZE or (
        len(rows) != FIVE_PLAYER_LINEUP_SIZE
    ):
        raise ValueError(
            f"app_frozen_lineup_must_have_{FIVE_PLAYER_LINEUP_SIZE}_players:"
            f"have={summary.player_count}"
        )
    try:
        by_slot = sorted(rows, key=lambda r: int(r["slot"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("app_frozen_lineup_requires_integer_slots") from exc
    slots = [int(r["slot"]) for r in by_slot]
    if slots != list(range(1, FIVE_PLAYER_LINEUP_SIZE + 1)):
        raise ValueError(f"app_frozen_lineup_slots_must_be_1_to_5:got={slots}")
    out: list[dict[str, Any]] = []
    for row in by_slot:
        card_row: dict[str, Any] = {
            "slot": int(row["slot"]),
            "player_id": row.get("player_id"),
            "name": row.get("name"),
            "team": row.get("team"),
            "value": row.get("value"),
        }
        for key in _CARD_EXTRA_KEYS:
            if row.get(key) is not None:
                card_row[key] = row[key]
        out.append(card_row)
    return tuple(out)


def lineup_for_summary(summary: BoardSummary) -> tuple[dict[str, Any], ...]:
    """App-frozen boards keep the app's five; other boards rank by value."""

    if summary.section == APP_FROZEN_SECTION:
        return frozen_app_lineup(summary)
    return five_player_lineup(summary)


def lineup_prompt_block(lineup: tuple[dict[str, Any], ...]) -> str:
    lines = [
        (
            f"DAILY CONTEST CARD (exactly {FIVE_PLAYER_LINEUP_SIZE} players, "
            "ordered slots 1..5; never fewer, never more):"
        ),
        (
            "Slot multipliers: "
            + ", ".join(
                f"slot{i}={m}x"
                for i, m in enumerate(OBSERVED_SLOT_MULTIPLIERS, start=1)
            )
        ),
        f"PRINCIPLE: {CHALK_VS_MULTIPLIER_PRINCIPLE}",
    ]
    for row in lineup:
        line = (
            f"  slot {row['slot']}: {row.get('name') or row.get('player_id')} "
            f"team={row.get('team') or ''} value={row.get('value')}"
        )
        if row.get("card_boost") is not None:
            line += f" card_boost={row.get('card_boost')}"
        if "real_score" in row:
            line += f" real_score={row.get('real_score')}"
        lines.append(line)
    return "\n".join(lines)
