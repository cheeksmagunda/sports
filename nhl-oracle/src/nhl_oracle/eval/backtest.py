"""HV board backtest helpers for NHL (observation only).

Grade picks against ``highestBoostedValuePlayers`` top-5 under contest
algebra. Never grade against winning drafts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from nhl_oracle.contest.algebra import (
    LineupScore,
    hindsight_optimal_assignment,
    score_ordered_lineup,
)
from nhl_oracle.contest.pick import FivePlayerPick
from nhl_oracle.contract.boost_gate import BoostEligibility
from nhl_oracle.labels.hv import TRAINING_LABEL_SECTION, HvBoardExtract, HvBoardRow


@dataclass(frozen=True)
class HvBacktestResult:
    """One contest graded against the HV board reference."""

    contest_id: int
    section: str
    reference_player_ids: tuple[int, ...]
    pick_player_ids: tuple[int, ...]
    reference_score: float
    pick_score: float
    capture_ratio: float
    boost_gated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "contest_id": self.contest_id,
            "section": self.section,
            "reference_player_ids": list(self.reference_player_ids),
            "pick_player_ids": list(self.pick_player_ids),
            "reference_score": self.reference_score,
            "pick_score": self.pick_score,
            "capture_ratio": self.capture_ratio,
            "boost_gated": self.boost_gated,
            "train_label_section": TRAINING_LABEL_SECTION,
            "observation_only": True,
            "contest_entry": False,
        }


def _values_from_rows(rows: Sequence[HvBoardRow]) -> dict[int, float]:
    return {row.player_id: row.value for row in rows}


def _boosts_from_rows(rows: Sequence[HvBoardRow]) -> dict[int, float]:
    return {row.player_id: row.card_boost for row in rows}


def backtest_pick_against_hv(
    extract: HvBoardExtract,
    pick: FivePlayerPick | Sequence[int],
    *,
    eligibility: BoostEligibility | None = None,
    boost_multiplier: float | None = None,
) -> HvBacktestResult:
    """Compare a five-player pick to the HV board top-5 under NHL algebra."""

    if not extract.has_train_labels:
        raise ValueError(f"hv_backtest_unavailable:{extract.status}")
    if len(extract.rows) < 5:
        raise ValueError("hv_board_fewer_than_5_players")

    ref_rows = extract.rows[:5]
    ref_ids = tuple(row.player_id for row in ref_rows)
    values = _values_from_rows(extract.rows)
    boosts = _boosts_from_rows(extract.rows)

    if isinstance(pick, FivePlayerPick):
        pick_ids = pick.player_ids
    else:
        pick_ids = tuple(int(x) for x in pick)
    if len(pick_ids) != 5:
        raise ValueError("pick_must_have_exactly_5_players")

    reference: LineupScore = hindsight_optimal_assignment(
        ref_ids,
        values,
        card_boosts=boosts,
        eligibility=eligibility,
        boost_multiplier=boost_multiplier,
    )
    # Grade the committed pick order as frozen (do not hindsight-reorder).
    pick_score: LineupScore = score_ordered_lineup(
        pick_ids,
        values,
        card_boosts=boosts,
        eligibility=eligibility,
        boost_multiplier=boost_multiplier,
    )
    ratio = pick_score.total_score / reference.total_score if reference.total_score else 0.0
    return HvBacktestResult(
        contest_id=extract.contest_id,
        section=extract.section_name or TRAINING_LABEL_SECTION,
        reference_player_ids=ref_ids,
        pick_player_ids=pick_ids,
        reference_score=reference.total_score,
        pick_score=pick_score.total_score,
        capture_ratio=ratio,
        boost_gated=reference.boost_gated,
    )


def projected_values_from_mapping(raw: Mapping[int, float]) -> dict[int, float]:
    """Copy projection map without coercing missing players to 0.0."""

    out: dict[int, float] = {}
    for pid, value in raw.items():
        if value != value:  # NaN
            raise ValueError(f"projected_value_nan:{pid}")
        out[int(pid)] = float(value)
    return out
