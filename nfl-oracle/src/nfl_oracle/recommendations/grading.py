"""Immutable post-slate grading for frozen NFL recommendations.

Grading consumes the stored freeze payload and finalized historical labels. It
never consults current candidates, projections, ownership, or optimization
logic, so a later data refresh cannot reorder or replace a frozen pick.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from nfl_oracle.recommendations.model import HistoricalPerformance
from nfl_oracle.recommendations.schema import Finite, PositiveId, Record, fingerprint


class GradedPick(Record):
    player_id: PositiveId
    game_id: PositiveId
    slot: int = Field(ge=1, le=5)
    slot_multiplier: Finite
    player_boost: Finite = Field(ge=0, le=3)
    actual_real_score: Finite
    total_value: Finite
    label_provenance: Literal["real_value_postgame_finalized"] = "real_value_postgame_finalized"


class GradeReport(Record):
    schema_version: Literal[1] = 1
    freeze_digest: str
    contest_id: PositiveId
    slate_date: date
    status: Literal["complete", "incomplete"]
    picks: tuple[GradedPick, ...]
    finalized_count: int = Field(ge=0, le=5)
    expected_count: int = Field(default=5, ge=5, le=5)
    missing_player_ids: tuple[int, ...] = ()
    total_value: Finite | None = None
    provenance: tuple[str, ...] = ()

    @model_validator(mode="after")
    def complete_totals(self) -> GradeReport:
        if self.status == "complete":
            if self.finalized_count != 5 or self.missing_player_ids or self.total_value is None:
                raise ValueError("complete_grade_requires_five_finalized_labels")
        elif self.total_value is not None:
            raise ValueError("incomplete_grade_cannot_claim_total")
        return self


class ReplayEntry(Record):
    freeze_digest: str
    status: Literal["complete", "incomplete"]
    total_value: Finite | None = None
    rank: int | None = Field(default=None, ge=1)


class LeaderboardReplay(Record):
    schema_version: Literal[1] = 1
    contest_id: PositiveId
    slate_date: date
    status: Literal["complete", "incomplete"]
    entries: tuple[ReplayEntry, ...]
    frozen_freeze_digest: str
    best_total_value: Finite | None = None
    holdout_regret: Finite | None = None
    provenance: tuple[str, ...] = ()


def _freeze_payload(
    freeze: Mapping[str, object],
) -> tuple[str, int, date, list[Mapping[str, object]]]:
    digest = freeze.get("digest")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("freeze_digest_required")
    body = {key: value for key, value in freeze.items() if key != "digest"}
    if fingerprint(body) != digest:
        raise ValueError("frozen_record_integrity_failure")
    contest_id = freeze.get("contest_id")
    day = freeze.get("slate_date")
    lineup = freeze.get("lineup")
    picks = lineup.get("picks") if isinstance(lineup, Mapping) else None
    if type(contest_id) is not int or contest_id <= 0 or not isinstance(day, str):
        raise ValueError("invalid_freeze_identity")
    if (
        not isinstance(picks, list)
        or len(picks) != 5
        or any(not isinstance(p, Mapping) for p in picks)
    ):
        raise ValueError("frozen_lineup_requires_five_picks")
    try:
        parsed_day = date.fromisoformat(day)
    except ValueError as error:
        raise ValueError("invalid_freeze_date") from error
    return digest, contest_id, parsed_day, picks


def grade_frozen_lineup(
    freeze: Mapping[str, object], performances: Sequence[HistoricalPerformance]
) -> GradeReport:
    """Grade exactly the IDs, slots, and boosts persisted by ``RecommendationStore``."""
    digest, contest_id, slate_date, picks = _freeze_payload(freeze)
    frozen: list[tuple[int, int, int, float, float]] = []
    slots: set[int] = set()
    ids: set[int] = set()
    for pick in picks:
        player_id = pick.get("player_id")
        game_id = pick.get("game_id")
        slot = pick.get("slot")
        boost = pick.get("card_boost")
        multiplier = pick.get("slot_multiplier")
        if (
            type(player_id) is not int
            or player_id <= 0
            or type(game_id) is not int
            or game_id <= 0
            or type(slot) is not int
            or not 1 <= slot <= 5
            or not isinstance(boost, (int, float))
            or not 0 <= boost <= 3
            or not isinstance(multiplier, (int, float))
        ):
            raise ValueError("frozen_scoring_fields_required")
        if player_id in ids or slot in slots:
            raise ValueError("frozen_lineup_duplicate_identity")
        ids.add(player_id)
        slots.add(slot)
        frozen.append((player_id, game_id, slot, float(boost), float(multiplier)))
    if slots != {1, 2, 3, 4, 5}:
        raise ValueError("frozen_lineup_slots_required")
    labels: dict[tuple[int, int], HistoricalPerformance] = {}
    for row in performances:
        key = (row.player_id, row.game_id)
        if key in labels:
            raise ValueError("duplicate_finalized_performance")
        labels[key] = row
    graded: list[GradedPick] = []
    missing: list[int] = []
    for player_id, game_id, slot, boost, multiplier in sorted(frozen, key=lambda item: item[2]):
        label: HistoricalPerformance | None = labels.get((player_id, game_id))
        if label is None:
            missing.append(player_id)
            continue
        if label.available_at <= label.kickoff_at:
            missing.append(player_id)
            continue
        graded.append(
            GradedPick(
                player_id=player_id,
                game_id=game_id,
                slot=slot,
                slot_multiplier=multiplier,
                player_boost=boost,
                actual_real_score=label.value,
                total_value=label.value * (multiplier + boost),
            )
        )
    complete = not missing and len(graded) == 5
    return GradeReport(
        freeze_digest=digest,
        contest_id=contest_id,
        slate_date=slate_date,
        status="complete" if complete else "incomplete",
        picks=tuple(graded),
        finalized_count=len(graded),
        missing_player_ids=tuple(missing),
        total_value=sum(p.total_value for p in graded) if complete else None,
        provenance=(
            "frozen_ids_slots_and_boosts",
            "real_value_postgame_finalized",
            "no_post_freeze_reassignment",
        ),
    )


def replay_leaderboard(
    frozen_lineup: Mapping[str, object],
    performances: Sequence[HistoricalPerformance],
    competitors: Sequence[Mapping[str, object]] = (),
) -> LeaderboardReplay:
    """Replay already-frozen lineups and calculate slate-level holdout regret.

    ``competitors`` must be frozen records from the same slate. The function
    compares realized totals only; it never synthesizes a better lineup.
    """
    records = [frozen_lineup, *competitors]
    reports = [grade_frozen_lineup(record, performances) for record in records]
    first = reports[0]
    if any((r.contest_id, r.slate_date) != (first.contest_id, first.slate_date) for r in reports):
        raise ValueError("replay_slate_mismatch")
    complete = all(r.status == "complete" for r in reports)
    totals = [r.total_value for r in reports]
    ranked = sorted(
        ((index, value) for index, value in enumerate(totals) if value is not None),
        key=lambda item: (-float(item[1]), item[0]),
    )
    ranks: dict[int, int] = {index: rank for rank, (index, _) in enumerate(ranked, 1)}
    entries = tuple(
        ReplayEntry(
            freeze_digest=report.freeze_digest,
            status=report.status,
            total_value=report.total_value,
            rank=ranks.get(index) if complete else None,
        )
        for index, report in enumerate(reports)
    )
    target = reports[0].total_value
    best = max((value for value in totals if value is not None), default=None)
    return LeaderboardReplay(
        contest_id=first.contest_id,
        slate_date=first.slate_date,
        status="complete" if complete else "incomplete",
        entries=entries,
        frozen_freeze_digest=first.freeze_digest,
        best_total_value=best if complete else None,
        holdout_regret=(
            best - target if complete and target is not None and best is not None else None
        ),
        provenance=(
            "frozen_lineup_replay",
            "slate_level_realized_total_value",
            "regret_is_relative_to_supplied_frozen_lineups",
        ),
    )


def holdout_regret(
    frozen_lineup: Mapping[str, object],
    performances: Sequence[HistoricalPerformance],
    competitors: Sequence[Mapping[str, object]] = (),
) -> float | None:
    """Convenience accessor for slate-level regret without lineup mutation."""
    return replay_leaderboard(frozen_lineup, performances, competitors).holdout_regret
