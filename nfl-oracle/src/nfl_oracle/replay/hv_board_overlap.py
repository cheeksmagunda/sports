"""Highest-value board shape versus chalk, on one visible board.

The Daily Draft Stats Highest value row is

``displayed_value ~= base * (slot_multiplier(most_common_slot) + boost)``

with slots 2.0 / 1.8 / 1.6 / 1.4 / 1.2. Chalk on that same row is draft count.
The two rankings are not the same list.

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
    _within_position_caps,
)
from nfl_oracle.recommendations.picker_knobs import _boost_aligned_means

SLOT_MULTIPLIERS: tuple[float, ...] = (2.0, 1.8, 1.6, 1.4, 1.2)
SLOT_BY_LABEL = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5}
POLICY = ScoringPolicy()


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


def top_names(rows: Sequence[BoardRow], *, key: str, n: int = 5) -> tuple[str, ...]:
    if key == "displayed":
        ordered = sorted(rows, key=lambda row: (-row.displayed_value, -row.draft_count, row.name))
    elif key == "drafts":
        ordered = sorted(rows, key=lambda row: (-row.draft_count, -row.displayed_value, row.name))
    else:
        raise ValueError("rank_key_unknown")
    return tuple(row.name for row in ordered[:n])


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


def _realized_score(players: Sequence[BoardRow], means: dict[int, float]) -> float:
    """Score the chosen five on realized base, slots ordered by the projection."""

    ordered = sorted(players, key=lambda row: (-means[row.player_id], row.player_id))
    return sum(
        POLICY.score(row.base, slot, row.boost)
        for row, slot in zip(ordered, SLOT_MULTIPLIERS, strict=True)
    )


def best_lineup(
    rows: Sequence[BoardRow],
    means: dict[int, float],
    *,
    max_defenders: int | None = None,
    max_kickers: int | None = None,
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


def overlap(left: Sequence[str], right: Sequence[str]) -> int:
    return len(set(left) & set(right))


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
    chalk_top5_hits: int
    realized_score: float
    capture_vs_uncapped: float
    kickers: int
    defenders: int


def score_board(rows: Sequence[BoardRow], *, regime: str) -> dict[str, object]:
    """Perfect-base counterfactual on this board. Not a fitted model frequency."""

    hv = top_names(rows, key="displayed")
    chalk = top_names(rows, key="drafts")
    residuals = [abs(law_value(row) - row.displayed_value) for row in rows]
    identity_means = projected_means(rows, blend=0.0)
    blend_means = projected_means(rows, blend=0.75)
    uncapped = best_lineup(rows, identity_means)
    uncapped_score = _realized_score(uncapped, identity_means)
    policies: list[tuple[str, dict[int, float], int | None, int | None]] = [
        ("identity_uncapped", identity_means, None, None),
        ("boost_0.75_uncapped", blend_means, None, None),
        ("boost_0.75_def1", blend_means, 1, None),
        ("boost_0.75_k1", blend_means, None, 1),
        ("boost_0.75_def1_k1", blend_means, 1, 1),
    ]
    scored: list[PolicyScore] = []
    for name, means, max_def, max_k in policies:
        picks = best_lineup(rows, means, max_defenders=max_def, max_kickers=max_k)
        names = tuple(row.name for row in picks)
        realized = _realized_score(picks, means)
        counts = position_counts(rows, names)
        scored.append(
            PolicyScore(
                name=name,
                picks=names,
                hv_top5_hits=overlap(names, hv),
                chalk_top5_hits=overlap(names, chalk),
                realized_score=realized,
                capture_vs_uncapped=realized / uncapped_score if uncapped_score else 0.0,
                kickers=counts["kickers"],
                defenders=counts["defenders"],
            )
        )
    chalk_picks = chalk
    chalk_rows = [row for row in rows if row.name in set(chalk_picks)]
    chalk_means = {row.player_id: row.base for row in chalk_rows}
    chalk_realized = _realized_score(chalk_rows, chalk_means)
    return {
        "regime": regime,
        "pool": "highest_value_section",
        "pool_size": len(rows),
        "full_roster": False,
        "law_max_abs_residual": max(residuals) if residuals else None,
        "law_mean_abs_residual": (sum(residuals) / len(residuals)) if residuals else None,
        "hv_top5": list(hv),
        "chalk_top5": list(chalk),
        "hv_chalk_overlap": overlap(hv, chalk),
        "hv_top5_positions": position_counts(rows, hv),
        "chalk_top5_positions": position_counts(rows, chalk),
        "uncapped_optimal_score": uncapped_score,
        "chalk_lineup_score": chalk_realized,
        "policies": [
            {
                "name": item.name,
                "picks": list(item.picks),
                "hv_top5_hits": item.hv_top5_hits,
                "chalk_top5_hits": item.chalk_top5_hits,
                "realized_score": item.realized_score,
                "capture_vs_uncapped": item.capture_vs_uncapped,
                "kickers": item.kickers,
                "defenders": item.defenders,
            }
            for item in scored
        ],
    }
