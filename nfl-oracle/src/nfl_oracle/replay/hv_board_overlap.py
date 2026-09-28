"""Score lineups only against a Highest-value / Total-value board.

The Daily Draft Stats Highest value row is

``displayed_value ~= base * (slot_multiplier(most_common_slot) + boost)``

with slots 2.0 / 1.8 / 1.6 / 1.4 / 1.2. Success is membership in that board's
top 5 and the share of the board's own Value total those hits carry.
Draft count, chalk, and win frequency are not success metrics.

This module scores a transcribed board. It does not invent a full-roster
frequency. The pool is the rows on the board.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

from nfl_oracle.recommendations.model import Projection
from nfl_oracle.recommendations.optimizer import (
    KICKER_POSITIONS,
    ScoringPolicy,
    _is_defender,
    _is_kicker,
)
from nfl_oracle.recommendations.picker_knobs import _boost_aligned_means

SLOT_MULTIPLIERS: tuple[float, ...] = (2.0, 1.8, 1.6, 1.4, 1.2)
SLOT_BY_LABEL = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5}
POLICY = ScoringPolicy()

def _within_position_caps(
    positions: Sequence[str],
    *,
    max_defenders: int = 0,
    max_kickers: int = 0,
) -> bool:
    """Research caps: ``0`` disables. Matches optimizer ``max_*=0`` semantics."""

    if max_kickers > 0 and sum(_is_kicker(position) for position in positions) > max_kickers:
        return False
    if max_defenders > 0 and sum(_is_defender(position) for position in positions) > max_defenders:
        return False
    return True



@dataclass(frozen=True)
class BoardRow:
    player_id: int
    name: str
    position: str
    team: str
    base: float
    boost: float
    most_common_slot: int
    draft_count: int
    displayed_value: float


def slot_multiplier(slot: int) -> float:
    if not 1 <= slot <= len(SLOT_MULTIPLIERS):
        raise ValueError("slot_out_of_range")
    return SLOT_MULTIPLIERS[slot - 1]


def law_value(row: BoardRow) -> float:
    """Value at the field's most common slot, the board's own column."""

    return row.base * (slot_multiplier(row.most_common_slot) + row.boost)


def parse_slot(label: str) -> int:
    key = label.strip().lower()
    if key not in SLOT_BY_LABEL:
        raise ValueError(f"slot_label_unknown:{label}")
    return SLOT_BY_LABEL[key]


def parse_draft_count(raw: str | int) -> int:
    if isinstance(raw, int):
        return raw
    text = raw.strip().lower().replace(",", "")
    if text.endswith("k"):
        return int(round(float(text[:-1]) * 1000))
    return int(text)


def top_names(rows: Sequence[BoardRow], *, n: int = 5) -> tuple[str, ...]:
    """Highest value board order. Ties break on player id, never on drafts."""

    ordered = sorted(rows, key=lambda row: (-row.displayed_value, row.player_id))
    return tuple(row.name for row in ordered[:n])


def hv_board_success(
    chosen: Sequence[int],
    board: Sequence[tuple[int, float]],
    *,
    n: int = 5,
) -> tuple[int | None, float | None]:
    """Hits and Value capture against an HV/TDV board.

    ``board`` is ``(player_id, displayed_value)`` rows. Capture is the sum of
    board Values for chosen players who sit in the top ``n``, divided by the
    top ``n`` Value total. Players outside that top ``n`` add nothing.
    Returns ``(None, None)`` when the board is empty.
    """

    ranked = sorted(board, key=lambda item: (-item[1], item[0]))[:n]
    if not ranked:
        return None, None
    chosen_ids = set(chosen)
    hits = sum(player_id in chosen_ids for player_id, _value in ranked)
    ceiling = sum(value for _player_id, value in ranked)
    if ceiling <= 0:
        return hits, None
    captured = sum(value for player_id, value in ranked if player_id in chosen_ids)
    return hits, captured / ceiling


def _projection(row: BoardRow) -> Projection:
    return Projection(
        player_id=row.player_id,
        mean=row.base,
        stddev=0.0,
        conditional_mean=row.base,
        availability_probability=1.0,
        prior_games=1,
        samples=(row.base,),
        provenance=("hv_board_base",),
    )


def projected_means(rows: Sequence[BoardRow], *, blend: float) -> dict[int, float]:
    """Identity keeps realized base. A blend reassigns that multiset by boost."""

    if len({row.player_id for row in rows}) != len(rows):
        raise ValueError("board_player_id_collision")
    base = {row.player_id: row.base for row in rows}
    if blend == 0.0:
        return base
    projections = tuple(_projection(row) for row in rows)
    aligned = _boost_aligned_means(projections, {row.player_id: row.boost for row in rows})
    return {
        row.player_id: (1.0 - blend) * base[row.player_id] + blend * aligned[row.player_id]
        for row in rows
    }


def _lineup_score(players: Sequence[BoardRow], means: dict[int, float]) -> float:
    ordered = sorted(players, key=lambda row: (-means[row.player_id], row.player_id))
    return sum(
        POLICY.score(means[row.player_id], slot, row.boost)
        for row, slot in zip(ordered, SLOT_MULTIPLIERS, strict=True)
    )


def best_lineup(
    rows: Sequence[BoardRow],
    means: dict[int, float],
    *,
    max_defenders: int = 0,
    max_kickers: int = 0,
) -> tuple[BoardRow, ...]:
    best: tuple[BoardRow, ...] | None = None
    best_score = float("-inf")
    for combo in combinations(rows, 5):
        positions = [row.position for row in combo]
        if not _within_position_caps(
            positions, max_defenders=max_defenders, max_kickers=max_kickers
        ):
            continue
        score = _lineup_score(combo, means)
        names = tuple(sorted(row.name for row in combo))
        best_names = tuple(sorted(row.name for row in best)) if best is not None else None
        better = score > best_score + 1e-9
        tied = abs(score - best_score) <= 1e-9 and (best_names is None or names < best_names)
        if better or tied:
            best = combo
            best_score = score
    if best is None:
        raise ValueError("no_legal_lineup")
    return tuple(sorted(best, key=lambda row: (-means[row.player_id], row.name)))


def position_counts(rows: Sequence[BoardRow], names: Sequence[str]) -> dict[str, int]:
    by_name = {row.name: row for row in rows}
    chosen = [by_name[name] for name in names]
    return {
        "kickers": sum(_is_kicker(row.position) for row in chosen),
        "defenders": sum(_is_defender(row.position) for row in chosen),
        "skill": sum(
            row.position.upper() not in KICKER_POSITIONS and not _is_defender(row.position)
            for row in chosen
        ),
    }


@dataclass(frozen=True)
class PolicyScore:
    name: str
    picks: tuple[str, ...]
    hv_top5_hits: int
    hv_board_capture: float
    kickers: int
    defenders: int


def _board_pairs(rows: Sequence[BoardRow]) -> tuple[tuple[int, float], ...]:
    return tuple((row.player_id, row.displayed_value) for row in rows)


def score_board(rows: Sequence[BoardRow], *, regime: str) -> dict[str, object]:
    """Perfect-base counterfactual. Success is the HV/TDV board only."""

    hv = top_names(rows)
    board = _board_pairs(rows)
    residuals = [abs(law_value(row) - row.displayed_value) for row in rows]
    identity_means = projected_means(rows, blend=0.0)
    blend_means = projected_means(rows, blend=0.75)
    policies: list[tuple[str, dict[int, float], int, int]] = [
        ("identity_uncapped", identity_means, 0, 0),
        ("boost_0.75_uncapped", blend_means, 0, 0),
        ("boost_0.75_def1", blend_means, 1, 0),
        ("boost_0.75_k1", blend_means, 0, 1),
        ("boost_0.75_def1_k1", blend_means, 1, 1),
    ]
    by_id = {row.player_id: row for row in rows}
    scored: list[PolicyScore] = []
    for name, means, max_def, max_k in policies:
        picks = best_lineup(rows, means, max_defenders=max_def, max_kickers=max_k)
        ids = tuple(row.player_id for row in picks)
        hits, capture = hv_board_success(ids, board)
        names = tuple(by_id[player_id].name for player_id in ids)
        counts = position_counts(rows, names)
        scored.append(
            PolicyScore(
                name=name,
                picks=names,
                hv_top5_hits=0 if hits is None else hits,
                hv_board_capture=0.0 if capture is None else capture,
                kickers=counts["kickers"],
                defenders=counts["defenders"],
            )
        )
    return {
        "regime": regime,
        "pool": "highest_value_section",
        "pool_size": len(rows),
        "full_roster": False,
        "success_metric": "hv_tdv_board_top5",
        "law_max_abs_residual": max(residuals) if residuals else None,
        "law_mean_abs_residual": (sum(residuals) / len(residuals)) if residuals else None,
        "hv_top5": list(hv),
        "hv_top5_positions": position_counts(rows, hv),
        "policies": [
            {
                "name": item.name,
                "picks": list(item.picks),
                "hv_top5_hits": item.hv_top5_hits,
                "hv_board_capture": item.hv_board_capture,
                "kickers": item.kickers,
                "defenders": item.defenders,
            }
            for item in scored
        ],
    }
