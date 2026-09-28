"""Split a contest day into Sunday multi-game vs one-night.

Real Sports daily drafts are one contest per calendar day. A Sunday with the
early and late windows is ``sunday_multi`` even when SNF shares that date.
TNF, SNF-only, and MNF are ``one_night_*``. Those regimes are not one sample:
Sunday chalk and a one-game night do not share a knob reading.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from zoneinfo import ZoneInfo

from nfl_oracle.features.live import kickoff_slot_name

EASTERN = ZoneInfo("America/New_York")

SUNDAY_MULTI = "sunday_multi"
ONE_NIGHT_TNF = "one_night_tnf"
ONE_NIGHT_SNF = "one_night_snf"
ONE_NIGHT_MNF = "one_night_mnf"
ONE_GAME_OTHER = "one_game_other"
MULTI_OTHER = "multi_other"
UNSCHEDULED = "unscheduled"

ONE_NIGHT_REGIMES = (ONE_NIGHT_TNF, ONE_NIGHT_SNF, ONE_NIGHT_MNF)
OPERATOR_REGIMES = (SUNDAY_MULTI, *ONE_NIGHT_REGIMES)


def _kind(kickoff: datetime) -> str:
    if kickoff.tzinfo is None:
        return "other"
    eastern = kickoff.astimezone(EASTERN)
    slot = kickoff_slot_name(kickoff)
    if slot == "mnf":
        return "mnf"
    if slot == "snf":
        return "snf"
    if eastern.weekday() == 3:
        return "tnf"
    if slot in {"early", "late"}:
        return slot
    return "other"


def regime_from_kickoffs(kickoffs: Sequence[datetime]) -> str:
    """Classify the games that share one daily contest."""

    usable = [kickoff for kickoff in kickoffs if kickoff.tzinfo is not None]
    if not usable:
        return UNSCHEDULED
    kinds = [_kind(kickoff) for kickoff in usable]
    if len(usable) == 1:
        only = kinds[0]
        if only == "tnf":
            return ONE_NIGHT_TNF
        if only == "snf":
            return ONE_NIGHT_SNF
        if only == "mnf":
            return ONE_NIGHT_MNF
        return ONE_GAME_OTHER
    afternoon = sum(kind in {"early", "late"} for kind in kinds)
    if afternoon >= 2:
        return SUNDAY_MULTI
    return MULTI_OTHER
