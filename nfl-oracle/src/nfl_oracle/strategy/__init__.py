"""Observation-only strategy contracts; no provider or submission integration."""

from nfl_oracle.strategy.clocks import feature_clocks_ok, live_feature_allowed
from nfl_oracle.strategy.lineup import FiveCardLineup, validate_five_card
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
from nfl_oracle.strategy.snapshot import DecisionPosture

# Compat alias
LineupLegality = LegalityCheck

__all__ = [
    "LIVE_FEATURE_BLACKLIST",
    "DecisionPosture",
    "FiveCardAction",
    "FiveCardLineup",
    "LegalityCheck",
    "LineupLegality",
    "Posture",
    "ShadowDecisionSnapshot",
    "check_action",
    "clocks_allow_feature",
    "feature_clocks_ok",
    "live_feature_allowed",
    "strategy_document",
    "validate_five_card",
]
