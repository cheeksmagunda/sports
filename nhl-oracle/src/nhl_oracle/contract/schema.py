"""NHL contest contract shape confirmed against live Real Sports evidence.

Defaults below reflect Week 2 live read-only audit (#299) as corrected by the
pre-boost re-audit (#325): five-card ordered, per-contest lock, score label
"value", goalie eligible, and boost_regime none until every NHL team has
played. Historical contest 1901 draftStats may show flat multiplierBonus from
a later window; that must not drive the live pre-boost default. Re-open a
field to UNKNOWN/None only when a later live audit contradicts these facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

OPEN_QUESTION_FORMAT = "contest_format_five_card_ordered_vs_roster_construction"
OPEN_QUESTION_LOCK_SCOPE = "lock_scope_per_contest_vs_per_game"
OPEN_QUESTION_GOALIE_ELIGIBILITY = "goalie_eligibility_unconfirmed"
OPEN_QUESTION_BOOST_REGIME = "boost_regime_unconfirmed"
OPEN_QUESTION_SCORE_VALUE_LABEL = "score_value_label_unconfirmed"


class ContestFormat(StrEnum):
    FIVE_CARD_ORDERED = "five_card_ordered"
    ROSTER_CONSTRUCTION = "roster_construction"
    UNKNOWN = "unknown"


class LockScope(StrEnum):
    PER_CONTEST = "per_contest"
    PER_GAME = "per_game"
    UNKNOWN = "unknown"


class BoostRegime(StrEnum):
    NONE = "none"
    FLAT = "flat"
    POSITIONAL = "positional"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class NhlContestContract:
    """NHL contest contract shape (defaults from live Real Sports audit #299)."""

    sport: str = "nhl"
    format: ContestFormat = ContestFormat.FIVE_CARD_ORDERED
    lock_scope: LockScope = LockScope.PER_CONTEST
    boost_regime: BoostRegime = BoostRegime.NONE
    score_value_label: str | None = "value"
    roster_size: int = 5
    slot_multipliers: tuple[float, ...] | None = (2.0, 1.8, 1.6, 1.4, 1.2)
    goalie_eligible: bool | None = True

    def __post_init__(self) -> None:
        if self.roster_size <= 0:
            raise ValueError("roster_size_must_be_positive")
        if self.slot_multipliers is not None:
            if len(self.slot_multipliers) != self.roster_size:
                raise ValueError("slot_multipliers_length_must_match_roster_size")
            if any(multiplier <= 0 for multiplier in self.slot_multipliers):
                raise ValueError("slot_multipliers_must_be_positive")

    def open_questions(self) -> tuple[str, ...]:
        """Contract fields not yet confirmed against a live provider."""

        unresolved: list[str] = []
        if self.format is ContestFormat.UNKNOWN:
            unresolved.append(OPEN_QUESTION_FORMAT)
        if self.lock_scope is LockScope.UNKNOWN:
            unresolved.append(OPEN_QUESTION_LOCK_SCOPE)
        if self.goalie_eligible is None:
            unresolved.append(OPEN_QUESTION_GOALIE_ELIGIBILITY)
        if self.boost_regime is BoostRegime.UNKNOWN:
            unresolved.append(OPEN_QUESTION_BOOST_REGIME)
        if self.score_value_label is None:
            unresolved.append(OPEN_QUESTION_SCORE_VALUE_LABEL)
        return tuple(unresolved)


@dataclass(frozen=True)
class NhlCandidate:
    """One roster candidate observed in a contract-audit fixture."""

    player_id: int
    position: str
    score_value: float | None
    captured_at: str
    identity_resolved: bool = True
    identity_ambiguous: bool = False

    def __post_init__(self) -> None:
        if self.player_id <= 0:
            raise ValueError("player_id_must_be_positive")
        if not self.position:
            raise ValueError("position_required")


@dataclass(frozen=True)
class NhlAuditFixture:
    """A synthetic or redacted-real snapshot to audit against a contract."""

    contract: NhlContestContract
    candidates: tuple[NhlCandidate, ...]
    expected_roster_size: int

    def __post_init__(self) -> None:
        if self.expected_roster_size <= 0:
            raise ValueError("expected_roster_size_must_be_positive")
