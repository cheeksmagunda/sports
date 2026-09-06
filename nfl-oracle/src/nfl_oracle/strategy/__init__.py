"""Observation-only strategy contracts; no provider or submission integration."""

from nfl_oracle.strategy.algebra import (
    OBSERVED_DEFAULT_SLOT_MULTIPLIERS,
    ContestShadowScore,
    contest_score_to_json,
    contest_shadow_score,
    scoring_document,
)
from nfl_oracle.strategy.clocks import feature_clocks_ok, live_feature_allowed
from nfl_oracle.strategy.enumerate import (
    ORDERINGS_PER_SET,
    best_shadow_ordering,
    ordered_five_card_actions,
    rank_shadow_orderings,
)
from nfl_oracle.strategy.gates import EntryGateReport, evaluate_entry_gates
from nfl_oracle.strategy.lineup import FiveCardLineup, validate_five_card
from nfl_oracle.strategy.posture import current_posture, posture_from_readiness
from nfl_oracle.strategy.schema import (
    LIVE_FEATURE_BLACKLIST,
    FiveCardAction,
    LegalityCheck,
    Posture,
    ShadowDecisionSnapshot,
    check_action,
    clocks_allow_feature,
    strategy_document,
)
from nfl_oracle.strategy.scoring import ShadowScore, shadow_weighted_score
from nfl_oracle.strategy.snapshot import DecisionPosture

# Compat alias
LineupLegality = LegalityCheck

__all__ = [
    "LIVE_FEATURE_BLACKLIST",
    "DecisionPosture",
    "EntryGateReport",
    "FiveCardAction",
    "FiveCardLineup",
    "LegalityCheck",
    "LineupLegality",
    "OBSERVED_DEFAULT_SLOT_MULTIPLIERS",
    "Posture",
    "ShadowDecisionSnapshot",
    "ShadowScore",
    "ContestShadowScore",
    "check_action",
    "clocks_allow_feature",
    "contest_score_to_json",
    "contest_shadow_score",
    "current_posture",
    "evaluate_entry_gates",
    "feature_clocks_ok",
    "live_feature_allowed",
    "ordered_five_card_actions",
    "best_shadow_ordering",
    "rank_shadow_orderings",
    "ORDERINGS_PER_SET",
    "posture_from_readiness",
    "scoring_document",
    "shadow_weighted_score",
    "strategy_document",
    "validate_five_card",
]
