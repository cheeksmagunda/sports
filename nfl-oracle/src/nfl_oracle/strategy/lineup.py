"""Compat aliases for five-card structural helpers."""

from __future__ import annotations

from nfl_oracle.strategy.schema import FiveCardAction, LegalityCheck, check_action

FiveCardLineup = FiveCardAction


def validate_five_card(lineup: FiveCardAction) -> LegalityCheck:
    return check_action(lineup)


__all__ = [
    "FiveCardLineup",
    "FiveCardAction",
    "LegalityCheck",
    "validate_five_card",
    "check_action",
]
