"""Compat re-export for shadow snapshots."""

from nfl_oracle.strategy.schema import Posture, ShadowDecisionSnapshot

DecisionPosture = Posture

__all__ = ["DecisionPosture", "Posture", "ShadowDecisionSnapshot"]
