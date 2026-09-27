"""Five-player daily contest pick contract for Ollama HV/TDV (#574).

Real Sports contests here are always an ordered five-player lineup.
Every slate day the watcher must propose exactly FIVE_PLAYER_LINEUP_SIZE
distinct players; never fewer, never more.

Slot multipliers (observed RS default) amplify chalk-vs-value decisions:
slot 1 = 2.0x ... slot 5 = 1.2x. True HV/TDV belongs in high slots even
when chalk; soft chalk without HV is faded.
"""

from __future__ import annotations

from typing import Any

from ollama_hv_watcher.boards import BoardSummary

# Hard contest size: five players every day, every sport.
FIVE_PLAYER_LINEUP_SIZE = 5

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
    "multiplier slots even when chalk (high drafts/ownership); fade soft "
    "chalk that lacks HV; never chase ownership alone; low-draft + high-value "
    "leverage earns mid/high slots when the value is real."
)


def five_player_lineup(
    summary: BoardSummary,
    *,
    size: int = FIVE_PLAYER_LINEUP_SIZE,
) -> tuple[dict[str, Any], ...]:
    """Return the top ``size`` distinct ranked players as the daily pick.

    Raises ``ValueError`` when the board cannot fill a full five-player card.
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
        slot = len(out) + 1
        out.append(
            {
                "slot": slot,
                "slot_multiplier": OBSERVED_SLOT_MULTIPLIERS[slot - 1],
                "player_id": row.get("player_id"),
                "name": row.get("name"),
                "team": row.get("team"),
                "value": row.get("value"),
                "real_score": row.get("real_score"),
                "drafts": row.get("drafts"),
            }
        )
        if len(out) >= FIVE_PLAYER_LINEUP_SIZE:
            break
    if len(out) < FIVE_PLAYER_LINEUP_SIZE:
        raise ValueError(
            "need_five_players_every_day:"
            f"board={summary.path or summary.slate_key or '?'} "
            f"have={len(out)} need={FIVE_PLAYER_LINEUP_SIZE}"
        )
    return tuple(out)


def lineup_prompt_block(lineup: tuple[dict[str, Any], ...]) -> str:
    lines = [
        (
            f"DAILY CONTEST CARD (exactly {FIVE_PLAYER_LINEUP_SIZE} players, "
            "ordered slots 1..5; never fewer, never more):"
        ),
        (
            "Slot multipliers (contest scoring): "
            + ", ".join(
                f"slot{i}={m}x"
                for i, m in enumerate(OBSERVED_SLOT_MULTIPLIERS, start=1)
            )
        ),
        f"PRINCIPLE: {CHALK_VS_MULTIPLIER_PRINCIPLE}",
    ]
    for row in lineup:
        lines.append(
            f"  slot {row['slot']} ({row.get('slot_multiplier')}x): "
            f"{row.get('name') or row.get('player_id')} "
            f"team={row.get('team') or ''} value={row.get('value')} "
            f"real_score={row.get('real_score')} drafts={row.get('drafts')}"
        )
    return "\n".join(lines)
