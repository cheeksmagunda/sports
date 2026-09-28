"""Score HV boards: HV-rank five vs draft-count chalk vs hindsight ceiling.

Observation only. The scoring law is the verified non-negative branch:

    item_score = value * (slot_multiplier + card_boost)
    entry.score = sum(item_score)

Slot order is the optimal pairing (descending realized value with descending
slot multipliers). Draft counts choose the chalk five. They are never the
score. Issue #597.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from nfl_oracle.contests.field import counterfactual_best
from nfl_oracle.contests.hv_export import HV_SECTION
from nfl_oracle.contests.parse import ParsedContest
from nfl_oracle.contests.schema import DraftStatRow
from nfl_oracle.strategy.algebra import OBSERVED_DEFAULT_SLOT_MULTIPLIERS

LINEUP_SIZE = 5


@dataclass(frozen=True)
class CardScore:
    player_id: int
    slot_index: int
    value: float
    slot_multiplier: float
    card_boost: float
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "slot_index": self.slot_index,
            "value": self.value,
            "slot_multiplier": self.slot_multiplier,
            "card_boost": self.card_boost,
            "score": self.score,
        }


@dataclass(frozen=True)
class FiveScore:
    kind: str
    player_ids: tuple[int, ...]
    total: float
    cards: tuple[CardScore, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "player_ids": list(self.player_ids),
            "total": self.total,
            "cards": [card.to_dict() for card in self.cards],
        }


def hv_rank_ids(rows: Sequence[DraftStatRow], *, n: int = LINEUP_SIZE) -> tuple[int, ...]:
    """Top ``n`` players on the HV section by realized value, not draft count."""

    best: dict[int, float] = {}
    for row in rows:
        if row.section != HV_SECTION or row.value is None:
            continue
        prior = best.get(row.player_id)
        if prior is None or float(row.value) > prior:
            best[row.player_id] = float(row.value)
    ranked = sorted(best, key=lambda pid: (-best[pid], pid))
    return tuple(ranked[:n])


def chalk_rank_ids(rows: Sequence[DraftStatRow], *, n: int = LINEUP_SIZE) -> tuple[int, ...]:
    """Top ``n`` players by draft count across sections. Count is selection only."""

    best: dict[int, int] = {}
    for row in rows:
        if row.draft_count is None:
            continue
        prior = best.get(row.player_id)
        if prior is None or int(row.draft_count) > prior:
            best[row.player_id] = int(row.draft_count)
    ranked = sorted(best, key=lambda pid: (-best[pid], pid))
    return tuple(ranked[:n])


def score_five(
    player_ids: Sequence[int],
    *,
    values: dict[int, float],
    boosts: dict[int, float],
    slot_multipliers: Sequence[float],
    kind: str,
) -> FiveScore | None:
    """Score one five under optimal slot order. Missing values fail closed."""

    slots = tuple(float(slot) for slot in slot_multipliers)
    if len(player_ids) < LINEUP_SIZE or len(slots) < LINEUP_SIZE:
        return None
    chosen = tuple(player_ids[:LINEUP_SIZE])
    if any(pid not in values for pid in chosen):
        return None
    if any(values[pid] < 0 for pid in chosen):
        return None
    ordered = tuple(sorted(chosen, key=lambda pid: (-values[pid], pid)))
    descending_slots = tuple(sorted(slots[:LINEUP_SIZE], reverse=True))
    cards: list[CardScore] = []
    total = 0.0
    for index, pid in enumerate(ordered):
        value = float(values[pid])
        boost = float(boosts.get(pid, 0.0))
        slot_m = descending_slots[index]
        score = value * (slot_m + boost)
        total += score
        cards.append(
            CardScore(
                player_id=pid,
                slot_index=index,
                value=value,
                slot_multiplier=slot_m,
                card_boost=boost,
                score=round(score, 6),
            )
        )
    return FiveScore(kind=kind, player_ids=ordered, total=round(total, 6), cards=tuple(cards))


def replay_hv_board(parsed: ParsedContest) -> dict[str, Any] | None:
    """Score one contest when it has an HV section of at least five players."""

    hv_ids = hv_rank_ids(parsed.draft_stats)
    if len(hv_ids) < LINEUP_SIZE:
        return None
    values = {
        row.player_id: float(row.value)
        for row in parsed.draft_stats
        if row.section == HV_SECTION and row.value is not None
    }
    # Boosts from the HV section first, then any other section as fill-in.
    boosts: dict[int, float] = {}
    for row in parsed.draft_stats:
        if row.section == HV_SECTION:
            boosts[row.player_id] = float(row.card_boost)
    for row in parsed.draft_stats:
        boosts.setdefault(row.player_id, float(row.card_boost))
    slots = parsed.contest.slot_multipliers or OBSERVED_DEFAULT_SLOT_MULTIPLIERS
    hv = score_five(
        hv_ids, values=values, boosts=boosts, slot_multipliers=slots, kind="hv_rank_five"
    )
    chalk_ids = chalk_rank_ids(parsed.draft_stats)
    chalk_values = dict(values)
    for row in parsed.draft_stats:
        if row.value is not None:
            chalk_values.setdefault(row.player_id, float(row.value))
    chalk = score_five(
        chalk_ids,
        values=chalk_values,
        boosts=boosts,
        slot_multipliers=slots,
        kind="draft_count_chalk_five",
    )
    if hv is None or chalk is None:
        return None
    ceiling = counterfactual_best(parsed, slot_multipliers=slots)
    ceiling_score = None if ceiling is None else ceiling.score
    share = None
    if ceiling_score not in (None, 0):
        share = round(hv.total / float(ceiling_score), 6)
    record = parsed.contest
    return {
        "contest_id": record.contest_id,
        "slate_date": record.day.isoformat(),
        "season": record.season,
        "game_id": record.game_id,
        "hv_five": hv.to_dict(),
        "chalk_five": chalk.to_dict(),
        "hindsight": None
        if ceiling is None
        else {
            "score": ceiling.score,
            "player_ids": list(ceiling.player_ids),
            "n_players_considered": ceiling.n_players_considered,
            "complete_pool": ceiling.complete_pool,
        },
        "hv_minus_chalk": round(hv.total - chalk.total, 6),
        "hv_share_of_hindsight": share,
        "draft_count_is_label": False,
        "contest_entry": False,
    }


def summarize_replays(boards: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Mean totals across scored boards. Empty input stays honest."""

    def _mean(key: str) -> float | None:
        totals: list[float] = []
        for board in boards:
            block = board.get(key)
            if isinstance(block, dict) and isinstance(block.get("total"), (int, float)):
                totals.append(float(block["total"]))
            elif key == "hindsight" and isinstance(block, dict):
                score = block.get("score")
                if isinstance(score, (int, float)):
                    totals.append(float(score))
        if not totals:
            return None
        return round(sum(totals) / len(totals), 6)

    return {
        "boards_scored": len(boards),
        "mean_hv_total": _mean("hv_five"),
        "mean_chalk_total": _mean("chalk_five"),
        "mean_hindsight": _mean("hindsight"),
        "contest_entry": False,
    }
