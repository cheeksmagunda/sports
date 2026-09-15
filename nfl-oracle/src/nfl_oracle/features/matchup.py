"""Static NFL division membership for the ``is_divisional`` FeatureSpec.

Public knowledge, no provider call and no auth. The map is era-stable for the
whole 2002+ catalog: the 2002 realignment created the current eight divisions,
and no franchise has changed division since. The relocations inside that window
(STL -> LAR, SD -> LAC, OAK -> LV) kept their division, so a historical
abbreviation only needs to resolve to its current franchise code before the
division lookup. Pre-2002 abbreviations are deliberately not modelled.

``nfl_oracle.recommendations.context.normalize_team`` owns feed-level spelling
fixes for nflverse joins and stays season-accurate there. This module keeps its
own franchise resolution instead of widening that function, so roster and
team-stat keys are unaffected by relocation folding. It also keeps the package
boundary one-way: ``features`` must not import ``recommendations``.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

AFC_EAST: Final = "AFC East"
AFC_NORTH: Final = "AFC North"
AFC_SOUTH: Final = "AFC South"
AFC_WEST: Final = "AFC West"
NFC_EAST: Final = "NFC East"
NFC_NORTH: Final = "NFC North"
NFC_SOUTH: Final = "NFC South"
NFC_WEST: Final = "NFC West"

NFL_DIVISIONS: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        "BUF": AFC_EAST,
        "MIA": AFC_EAST,
        "NE": AFC_EAST,
        "NYJ": AFC_EAST,
        "BAL": AFC_NORTH,
        "CIN": AFC_NORTH,
        "CLE": AFC_NORTH,
        "PIT": AFC_NORTH,
        "HOU": AFC_SOUTH,
        "IND": AFC_SOUTH,
        "JAX": AFC_SOUTH,
        "TEN": AFC_SOUTH,
        "DEN": AFC_WEST,
        "KC": AFC_WEST,
        "LAC": AFC_WEST,
        "LV": AFC_WEST,
        "DAL": NFC_EAST,
        "NYG": NFC_EAST,
        "PHI": NFC_EAST,
        "WAS": NFC_EAST,
        "CHI": NFC_NORTH,
        "DET": NFC_NORTH,
        "GB": NFC_NORTH,
        "MIN": NFC_NORTH,
        "ATL": NFC_SOUTH,
        "CAR": NFC_SOUTH,
        "NO": NFC_SOUTH,
        "TB": NFC_SOUTH,
        "ARI": NFC_WEST,
        "LAR": NFC_WEST,
        "SEA": NFC_WEST,
        "SF": NFC_WEST,
    }
)

# Relocations and feed spellings seen on 2002+ Real Sports / nflverse rows.
# Every entry resolves to the franchise's current code; none crosses a
# division boundary, so the division lookup stays season-independent.
FRANCHISE_ALIASES: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        "ARZ": "ARI",
        "CRD": "ARI",
        "BLT": "BAL",
        "RAV": "BAL",
        "CLV": "CLE",
        "GNB": "GB",
        "HST": "HOU",
        "JAC": "JAX",
        "KAN": "KC",
        "LA": "LAR",
        "LAR": "LAR",
        "RAM": "LAR",
        "SL": "LAR",
        "STL": "LAR",
        "LVR": "LV",
        "OAK": "LV",
        "RAI": "LV",
        "SD": "LAC",
        "SDG": "LAC",
        "NOR": "NO",
        "NWE": "NE",
        "OTI": "TEN",
        "SFO": "SF",
        "TAM": "TB",
        "WFT": "WAS",
        "WSH": "WAS",
    }
)


def franchise_code(team: str | None) -> str | None:
    """Resolve a feed abbreviation to its current franchise code, or None."""

    if not team:
        return None
    raw = str(team).upper().strip()
    code = FRANCHISE_ALIASES.get(raw, raw)
    return code if code in NFL_DIVISIONS else None


def division_for_team(team: str | None) -> str | None:
    """Return the current division of ``team``, or None when unrecognized."""

    code = franchise_code(team)
    return NFL_DIVISIONS.get(code) if code is not None else None


def is_divisional_matchup(team: str | None, opponent: str | None) -> bool | None:
    """True when both teams share a division; None when either is unknown.

    A team is never its own divisional opponent: an unusable pair (same code on
    both sides) reports None rather than a fabricated True.
    """

    home = franchise_code(team)
    away = franchise_code(opponent)
    if home is None or away is None or home == away:
        return None
    return NFL_DIVISIONS[home] == NFL_DIVISIONS[away]
