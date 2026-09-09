"""Typed, validated records parsed out of saved Corpus C payloads.

Every field here is observed in a provider payload. Nothing is imputed. A field
the provider omits stays ``None`` so downstream censoring analysis can tell
"absent" from "zero".
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Finite = Annotated[float, Field(allow_inf_nan=False)]
PositiveId = Annotated[int, Field(gt=0, strict=True)]

# The five committed slot multipliers. Verified live on contests 870 and 2141.
OBSERVED_SLOT_MULTIPLIERS: tuple[float, float, float, float, float] = (2.0, 1.8, 1.6, 1.4, 1.2)
# Highest ``multiplierBonus`` observed in any saved contest. Used as a range
# guard, not as a modelling assumption.
MAX_OBSERVED_BOOST = 3.0
# ``/entries`` serves at most this many rows and exposes no pagination
# parameter. Every field statistic derived from entries is censored at this cut.
ENTRIES_VISIBLE_LIMIT = 20


class Record(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class PayoutTier(Record):
    """One row of the leaderboard prize table."""

    rank_display: str
    prize_amount: Finite


class RaxPoolOption(Record):
    """An optional side pool. These, not the leaderboard, carry the real payout."""

    key: str
    percent: Finite = Field(gt=0, le=1)
    payout_multiple: Finite = Field(gt=0)
    wager_options: tuple[int, ...] = ()


class ContestRecord(Record):
    """Contest-level facts. ``entrants`` is the provider's own field count."""

    contest_id: PositiveId
    sport: Literal["nfl"]
    day: date
    end_day: date
    season: int | None = None
    lineup_size: int = Field(ge=1)
    slot_multipliers: tuple[Finite, ...]
    entrants: int = Field(ge=0)
    is_finalized: bool
    is_locked: bool | None = None
    comment_count: int | None = None
    created_at: datetime | None = None
    processed_at: datetime | None = None
    game_id: int | None = None
    payout_tiers: tuple[PayoutTier, ...] = ()
    rax_pools: tuple[RaxPoolOption, ...] = ()
    captured_at: datetime

    @model_validator(mode="after")
    def coherent(self) -> ContestRecord:
        if self.end_day < self.day:
            raise ValueError("contest_day_range_invalid")
        return self

    @property
    def is_single_day(self) -> bool:
        return self.day == self.end_day


class EntryLineupPick(Record):
    """One of the five committed cards inside a saved human entry."""

    player_id: PositiveId
    slot: int = Field(ge=1)
    slot_multiplier: Finite = Field(gt=0)
    card_boost: Finite = Field(ge=0)
    effective_multiplier: Finite = Field(gt=0)
    value: Finite | None = None
    score: Finite | None = None
    real_rank: int | None = None
    is_exact: bool | None = None
    team_id: int | None = None
    display_name: str | None = None
    injury_status: str | None = None

    @model_validator(mode="after")
    def multiplier_decomposes(self) -> EntryLineupPick:
        """The scoring law is additive: effective = slot + boost, score = value * effective."""
        if abs(self.slot_multiplier + self.card_boost - self.effective_multiplier) > 1e-6:
            raise ValueError("multiplier_decomposition_mismatch")
        if self.value is not None and self.score is not None:
            if abs(self.value * self.effective_multiplier - self.score) > 1e-3:
                raise ValueError("score_law_mismatch")
        return self


class EntryRecord(Record):
    """A saved human lineup. Only the top ``ENTRIES_VISIBLE_LIMIT`` are served."""

    contest_id: PositiveId
    entry_id: PositiveId
    rank: int = Field(ge=1)
    score: Finite | None = None
    payout: Finite | None = None
    wager: Finite | None = None
    entry_type: str | None = None
    picks: tuple[EntryLineupPick, ...]

    @model_validator(mode="after")
    def slots_are_a_permutation(self) -> EntryRecord:
        slots = sorted(p.slot for p in self.picks)
        if slots != list(range(1, len(self.picks) + 1)):
            raise ValueError("entry_slots_not_a_permutation")
        if len({p.player_id for p in self.picks}) != len(self.picks):
            raise ValueError("entry_duplicate_player")
        return self

    def total_from_picks(self) -> float | None:
        """Recompute the leaderboard score from the parts, for law verification."""
        if any(p.score is None for p in self.picks):
            return None
        return sum(float(p.score or 0.0) for p in self.picks)


class DraftStatRow(Record):
    """Field-level draft behaviour for one player in one finalized contest.

    ``draft_count`` is the provider's own count for that player within the
    section it appeared in. Its denominator is not stated by the provider, so it
    is an ordinal popularity signal, never an ownership fraction.
    """

    contest_id: PositiveId
    player_id: PositiveId
    section: str
    card_boost: Finite = Field(ge=0)
    value: Finite | None = None
    draft_count: int | None = None
    avg_effective_multiplier: Finite | None = None
    avg_slot_position: Finite | None = None
    avg_score: Finite | None = None
    highest_score: Finite | None = None
    base_boosted_value: Finite | None = None
    most_common_slot: int | None = None
    count_at_highest_slot: int | None = None
    slot_of_highest_score: int | None = None
    team_id: int | None = None
    display_name: str | None = None

    @field_validator("most_common_slot", "slot_of_highest_score", mode="before")
    @classmethod
    def coerce_slot(cls, value: Any) -> Any:
        if value is None or isinstance(value, int):
            return value
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None
