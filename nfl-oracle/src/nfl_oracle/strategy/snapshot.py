"""Compat re-export for shadow snapshots."""

from nfl_oracle.strategy.schema import Posture, ShadowDecisionSnapshot
from nfl_oracle.strategy.schema import Posture as DecisionPosture

__all__ = ["DecisionPosture", "Posture", "ShadowDecisionSnapshot"]
