"""Observation-only strategy contracts; no provider submission.

Follows the Drive NFL strategy playbook: five ordered slots, train/live clocks,
leakage blacklist, and #91 shadow posture. Structural validity is not provider
legality, contest entry permission, or evidence of an edge.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from nfl_oracle.labels.schema import LIVE_FEATURE_BLACKLIST
from nfl_oracle.labels.schema import schema_document as label_schema_document

__all__ = [
    "LIVE_FEATURE_BLACKLIST",
    "FiveCardAction",
    "LegalityCheck",
    "Posture",
    "ShadowDecisionSnapshot",
    "check_action",
    "clocks_allow_feature",
    "strategy_document",
]


def _aware(value: str | datetime | None) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
        return stamp if stamp is not None and stamp.utcoffset() is not None else None
    except (TypeError, ValueError):
        return None


def clocks_allow_feature(
    *,
    feature_name: str,
    source_available_at: str | datetime | None,
    captured_at: str | datetime | None,
    decision_at: str | datetime | None,
    lock_at: str | datetime | None = None,
) -> bool:
    """Fail closed on blacklist / unknown clocks.

    Preferred live gate (playbook): source_available_at and captured_at <=
    decision_at, and decision_at < lock_at when lock_at is known. If lock_at is
    omitted, still require availability clocks <= decision_at.
    """

    if feature_name in LIVE_FEATURE_BLACKLIST or feature_name.startswith("same_slate_"):
        return False
    source = _aware(source_available_at)
    capture = _aware(captured_at)
    decision = _aware(decision_at)
    lock = _aware(lock_at)
    if source is None or capture is None or decision is None:
        return False
    if not (source <= decision and capture <= decision):
        return False
    if lock is not None and not (decision < lock):
        return False
    return True


class Posture(StrEnum):
    SHADOW_ONLY = "shadow_only"
    CAPTURE_ONLY = "capture_only"
    BLOCKED = "blocked"
    READY_PENDING_CONTRACT = "ready_pending_contract"


UNKNOWN_RULES = (
    "provider roster and inventory eligibility",
    "provider duplicate-card rules",
    "slot weights and scoring",
    "provider lock semantics",
    "multiplier_bonus_pre_lock_visibility_unknown",
    "negative_value_scoring_branch_unverified",
)


@dataclass(frozen=True)
class LegalityCheck:
    structural_errors: tuple[str, ...]
    unknown_rules: tuple[str, ...] = UNKNOWN_RULES

    @property
    def structurally_valid(self) -> bool:
        return not self.structural_errors

    @property
    def ok(self) -> bool:
        return self.structurally_valid


class FiveCardAction(BaseModel):
    """Ordered five-player action (Real player ids). Not a submission payload."""

    model_config = ConfigDict(extra="forbid")

    player_ids: tuple[int, int, int, int, int]
    slot_multipliers: tuple[float, float, float, float, float] | None = None
    notes: str = ""

    @field_validator("player_ids")
    @classmethod
    def _positive_ids(cls, value: tuple[int, int, int, int, int]) -> tuple[int, int, int, int, int]:
        if any(pid <= 0 for pid in value):
            raise ValueError("player_ids_must_be_positive")
        return value


def check_action(action: FiveCardAction) -> LegalityCheck:
    """Structural checks only — provider contest contract remains #91 open."""

    errors: list[str] = []
    ids = action.player_ids
    if len(ids) != 5:
        errors.append("expected_exactly_five_players")
    if len(set(ids)) != len(ids):
        errors.append("duplicate_player_ids")
    if action.slot_multipliers is not None:
        if len(action.slot_multipliers) != 5:
            errors.append("slot_multipliers_must_be_length_five")
        elif any(m <= 0 for m in action.slot_multipliers):
            errors.append("slot_multipliers_must_be_positive")
    return LegalityCheck(structural_errors=tuple(errors))


class ShadowDecisionSnapshot(BaseModel):
    """Immutable shadow observation record. contest_entry is always false."""

    model_config = ConfigDict(extra="forbid")

    decision_at: str
    posture: Posture = Posture.READY_PENDING_CONTRACT
    contest_id: int | None = None
    slate_id: str | None = None
    action: FiveCardAction | None = None
    baseline_scores: dict[str, float] = Field(default_factory=dict)
    notes: str = ""
    contest_entry: Literal[False] = False
    schema_version: int = 1

    @field_validator("contest_entry")
    @classmethod
    def _forbid_entry(cls, value: bool) -> bool:
        if value:
            raise ValueError("ShadowDecisionSnapshot forbids contest_entry=True")
        return False


def strategy_document() -> dict[str, Any]:
    """Machine-readable strategy scaffold for CLI/docs/service."""

    return {
        "name": "nfl_strategy_scaffold",
        "version": 1,
        "contest_entry": False,
        "posture_default": Posture.READY_PENDING_CONTRACT.value,
        "issue_refs": ["#89", "#91"],
        "clocks": {
            "live_gate": (
                "source_available_at and captured_at <= decision_at; "
                "decision_at < lock_at when lock known"
            ),
            "helper": "nfl_oracle.strategy.schema.clocks_allow_feature",
            "blacklist": list(LIVE_FEATURE_BLACKLIST),
        },
        "five_card": {
            "slots": 5,
            "orderings_per_set": 120,
            "legality": "structural_only_until_provider_contract_verified",
            "unknown_rules": list(UNKNOWN_RULES),
            "observed_default_slot_multipliers": [2.0, 1.8, 1.6, 1.4, 1.2],
            "scoring_helper": "nfl_oracle.strategy.algebra.contest_shadow_score",
        },
        "labels": label_schema_document(),
        "observation_only": True,
        "playbook": "drive/NFL-ORACLE Data Science Resources, Strategy, Research, and more.txt",
        "entry_gates": "nfl_oracle.strategy.gates.evaluate_entry_gates",
    }
