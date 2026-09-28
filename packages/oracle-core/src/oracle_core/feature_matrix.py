"""Portfolio FEATURE_MATRIX: available | wired | serving (#583).

``wire_available_to_freeze`` is the production switch. Rows with
``serve="on"`` copy numeric values from the app's available dict into the
freeze feature payload. Rows with ``serve="off"`` stay catalog-only
(leakage-blocked signals, or gold that is not on the freeze path yet).

Sport apps own provider parsing. This module only filters and copies keys.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Literal

SCHEMA_VERSION = 1

PathStatus = Literal["yes", "no", "partial", "leakage_blocked", "label_only"]
ServePolicy = Literal["on", "off"]

_SEASON_FEATURE = "seasonAverages.*"


@dataclass(frozen=True)
class FeatureRow:
    """One Real Sports or external signal in the freeze inventory."""

    feature: str
    sports: tuple[str, ...]
    source: str
    available: PathStatus
    wired: PathStatus
    serving: PathStatus
    freeze_surface: str
    notes: str
    freeze_keys: tuple[str, ...] = ()
    unused_gold: bool = False
    serve: ServePolicy = "off"
    # When set, prices copy only if this flag is a positive finite number.
    availability_flag: str = ""


FEATURE_MATRIX: tuple[FeatureRow, ...] = (
    FeatureRow(
        feature="Corpus G boxes / playerBoxScores.value",
        sports=("nfl", "nhl", "nba"),
        source="Real Sports game stats",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="NFL ridge/valuelaw priors + HV grade labels",
        notes="Primary Real value label. WNBA uses nba_api plus RS boxes.",
        serve="off",
    ),
    FeatureRow(
        feature="Corpus C contest / draftStats HV",
        sports=("wnba", "nfl", "nba", "nhl"),
        source="draftStats.highestBoostedValuePlayers",
        available="yes",
        wired="yes",
        serving="label_only",
        freeze_surface="train/grade Total Value boards; not a live feature",
        notes="Never winning drafts.",
        serve="off",
    ),
    FeatureRow(
        feature="draftStats.popularPlayers / mostCommon3x / mostDrafted",
        sports=("wnba", "nfl"),
        source="Daily Draft Stats non-HV sections",
        available="yes",
        wired="partial",
        serving="no",
        freeze_surface="recorded_states / slate_labels only",
        notes="Corpus inventory. Not a distinct freeze term.",
        unused_gold=True,
        serve="off",
    ),
    FeatureRow(
        feature="card_boost / multiplierBonus",
        sports=("wnba", "nfl", "nhl"),
        source="RS pool pre-lock",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="WNBA EB boost_beta + picker; NFL optimizer score",
        notes="Already fused on the freeze path outside this copier.",
        serve="off",
    ),
    FeatureRow(
        feature="vegas_total / vegas_spread",
        sports=("wnba",),
        source="The Odds API",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="EB vegas_total term; spread feeds game_script",
        notes="Already fused by job1. implied_team_total is not a separate EB term.",
        serve="off",
    ),
    FeatureRow(
        feature="h2h moneyline → team_moneyline",
        sports=("wnba", "nfl"),
        source="Odds API (WNBA) / RS game (NFL)",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="WNBA EB moneyline_beta; NFL REQUIRED_RS_POOL context",
        notes=(
            "Production ON (#583). job1 and NFL context copy prices when "
            "moneyline_available is positive. EB applies moneyline_beta when "
            "the loaded artifact has a non-zero coefficient."
        ),
        freeze_keys=("team_moneyline", "opponent_moneyline", "moneyline_available"),
        availability_flag="moneyline_available",
        serve="on",
    ),
    FeatureRow(
        feature="overallRank",
        sports=("wnba", "nfl"),
        source="RS pool cards",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="WNBA EB overall_rank_beta; NFL ridge context",
        notes="Copied when the pool row carries a finite rank.",
        freeze_keys=("overall_rank",),
        serve="on",
    ),
    FeatureRow(
        feature="RotoWire starters / is_confirmed_starter",
        sports=("wnba",),
        source="RotoWire free page",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="serve _starter_multiplier on EB / ladder",
        notes="Already fused by job1 starter flags.",
        serve="off",
    ),
    FeatureRow(
        feature="team_pace / opp_pace / game_pace_implied",
        sports=("wnba", "nfl"),
        source="rolling game_logs / Corpus G",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="WNBA EB pace betas; NFL pace priors",
        notes="",
        serve="off",
    ),
    FeatureRow(
        feature="live / measured ownership (drafts)",
        sports=("wnba", "nfl"),
        source="RS draftStats drafts + LIVE_OWNERSHIP_CAPTURE",
        available="yes",
        wired="yes",
        serving="partial",
        freeze_surface="field measured path when a pre-lock capture exists",
        notes="Same-slate post-lock drafts stay leakage-blocked.",
        unused_gold=True,
        serve="off",
    ),
    FeatureRow(
        feature="prop_points_over_prob (D78)",
        sports=("wnba",),
        source="Odds API player props",
        available="yes",
        wired="yes",
        serving="no",
        freeze_surface="_prop_signal_multiplier when PROP_SIGNAL_SCALE>0",
        notes="Code default scale is 0.0. Not flipped by the matrix.",
        unused_gold=True,
        serve="off",
    ),
    FeatureRow(
        feature=_SEASON_FEATURE,
        sports=("wnba", "nfl"),
        source="RS feed / pool",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="head_features / context season_avg_* on the freeze payload",
        notes=(
            "Production ON when the provider sends numeric seasonAverages. "
            "Keys land on the freeze feature dict. WNBA EB scores "
            "team_moneyline via moneyline_beta; season_avg_* have no separate "
            "beta on the current artifact."
        ),
        serve="on",
    ),
    FeatureRow(
        feature="gameTeamComparison.previousMeetings",
        sports=("nfl",),
        source="Corpus G stats",
        available="yes",
        wired="no",
        serving="no",
        freeze_surface="corpus dump only",
        notes="lastTenWins remains the wired standings leaf.",
        unused_gold=True,
        serve="off",
    ),
    FeatureRow(
        feature="contest_leaderboards winning drafts",
        sports=("wnba", "nfl"),
        source="RS leaderboards",
        available="yes",
        wired="partial",
        serving="leakage_blocked",
        freeze_surface="recorded_states observation only",
        notes="Never a primary train or serve target.",
        serve="off",
    ),
)


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(number):
        return None
    return number


def _season_key(raw_key: str) -> str:
    snake = re.sub(r"[^a-z0-9]+", "_", raw_key.strip().lower()).strip("_")
    if not snake:
        return ""
    return f"season_avg_{snake}"


def feature_matrix(*, sport: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in FEATURE_MATRIX:
        if sport is not None and sport not in row.sports:
            continue
        rows.append(asdict(row))
    return rows


def unused_gold(*, sport: str | None = None) -> list[dict[str, Any]]:
    return [row for row in feature_matrix(sport=sport) if row.get("unused_gold")]


def serving_rows(*, sport: str) -> tuple[FeatureRow, ...]:
    return tuple(row for row in FEATURE_MATRIX if sport in row.sports and row.serve == "on")


def wire_available_to_freeze(sport: str, available: Mapping[str, Any]) -> dict[str, float]:
    """Copy serve-on signals into a freeze feature dict.

    Missing values are omitted. A zero ``availability_flag`` records the flag
    and skips the row's other keys. ``serve="off"`` rows are never copied,
    including leakage-blocked names that happen to be present in ``available``.
    """

    out: dict[str, float] = {}
    for row in serving_rows(sport=sport):
        if row.feature == _SEASON_FEATURE:
            raw = available.get("season_averages")
            if not isinstance(raw, Mapping):
                continue
            for key, value in raw.items():
                number = _finite(value)
                season_key = _season_key(str(key))
                if number is None or not season_key:
                    continue
                out[season_key] = number
            continue
        flag = row.availability_flag
        if flag:
            flag_number = _finite(available.get(flag))
            if flag_number is None:
                continue
            out[flag] = 1.0 if flag_number > 0.0 else 0.0
            if flag_number <= 0.0:
                continue
        for key in row.freeze_keys:
            if key == flag:
                continue
            if key not in available or available[key] is None:
                continue
            number = _finite(available[key])
            if number is not None:
                out[key] = number
    return out


def matrix_document() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "vocabulary": {
            "available": "source can supply the signal",
            "wired": "persist path into a freeze-readable store",
            "serving": "freeze path can consume the signal for score or optimize",
            "serve": "on copies available numbers into the freeze payload",
        },
        "features": feature_matrix(),
        "unused_gold": unused_gold(),
        "issue": 583,
    }
