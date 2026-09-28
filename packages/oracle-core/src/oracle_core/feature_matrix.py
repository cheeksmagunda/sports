"""Portfolio FEATURE_MATRIX: available | wired | serving (#583).

Vocabulary, orthogonal to each app's rs_field_map mapped/gap/leakage:

- available: a provider or external source can supply the signal today
- wired: ingest or fuse code can persist it into a freeze-readable store
- serving: the freeze path consumes it for a prediction or an optimizer score

UNUSED_GOLD is available and not serving, excluding leakage-blocked labels.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

SCHEMA_VERSION = 1

PathStatus = Literal["yes", "no", "partial", "leakage_blocked", "label_only"]


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
    unused_gold: bool = False


FEATURE_MATRIX: tuple[FeatureRow, ...] = (
    FeatureRow(
        feature="Corpus G boxes / playerBoxScores.value",
        sports=("nfl", "nhl", "nba"),
        source="Real Sports game stats",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="NFL ridge and valuelaw priors; HV grade labels",
        notes="WNBA game logs come from nba_api plus Real Sports boxes.",
    ),
    FeatureRow(
        feature="Corpus C contest / draftStats HV",
        sports=("wnba", "nfl", "nba", "nhl"),
        source="draftStats.highestBoostedValuePlayers",
        available="yes",
        wired="yes",
        serving="label_only",
        freeze_surface="train and grade Total Value boards, not a live feature",
        notes="Never prior users' winning drafts.",
    ),
    FeatureRow(
        feature="draftStats.popularPlayers / mostCommon3x / mostDrafted",
        sports=("wnba", "nfl"),
        source="Daily Draft Stats non-HV sections",
        available="yes",
        wired="partial",
        serving="no",
        freeze_surface="recorded_states and slate_labels only",
        notes="Not a distinct model term.",
        unused_gold=True,
    ),
    FeatureRow(
        feature="card_boost / multiplierBonus",
        sports=("wnba", "nfl", "nhl"),
        source="Real Sports pool pre-lock",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="WNBA EB boost term and NFL optimizer score",
        notes="NHL early slates are often all-zero until every club has a GP.",
    ),
    FeatureRow(
        feature="vegas_total / vegas_spread",
        sports=("wnba",),
        source="The Odds API",
        available="yes",
        wired="yes",
        serving="partial",
        freeze_surface="EB vegas_total term; spread feeds game_script",
        notes="implied_team_total is classified but EB predict uses vegas_total.",
        unused_gold=True,
    ),
    FeatureRow(
        feature="h2h moneyline to team_moneyline",
        sports=("wnba", "nfl"),
        source="Odds API h2h (WNBA) or Real Sports game (NFL)",
        available="yes",
        wired="partial",
        serving="partial",
        freeze_surface="NFL ridge context; WNBA EB moneyline_beta when fused",
        notes=(
            "WNBA job1 writes h2h only when WNBA_FUSE_MONEYLINE is on. "
            "Default off. A zero moneyline_beta does not change the score."
        ),
        unused_gold=True,
    ),
    FeatureRow(
        feature="RotoWire starters / is_confirmed_starter",
        sports=("wnba",),
        source="RotoWire free page",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="serve starter multiplier on the EB path",
        notes="rotowire_empty is an advisory until tip-day starters post.",
    ),
    FeatureRow(
        feature="team_pace / opp_pace / game_pace_implied",
        sports=("wnba", "nfl"),
        source="rolling game logs or Corpus G",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="WNBA EB pace betas; NFL pace priors",
        notes="",
    ),
    FeatureRow(
        feature="prop_points_over_prob",
        sports=("wnba",),
        source="Odds API player props",
        available="yes",
        wired="yes",
        serving="partial",
        freeze_surface="prop signal multiplier when PROP_SIGNAL_SCALE is above 0",
        notes="Code default scale is 0. EXPECTED_PROD_CONFIG wants 0.3.",
        unused_gold=True,
    ),
    FeatureRow(
        feature="seasonAverages.*",
        sports=("wnba", "nfl"),
        source="Real Sports feed or pool",
        available="yes",
        wired="no",
        serving="no",
        freeze_surface="extract_season_averages exists and is not called on freeze",
        notes="rs_field_map status is unused.",
        unused_gold=True,
    ),
    FeatureRow(
        feature="gameTeamComparison.previousMeetings",
        sports=("nfl",),
        source="Corpus G stats",
        available="yes",
        wired="no",
        serving="no",
        freeze_surface="corpus dump only",
        notes="lastTenWins is the wired standings leaf.",
        unused_gold=True,
    ),
    FeatureRow(
        feature="contest_leaderboards winning drafts",
        sports=("wnba", "nfl"),
        source="Real Sports leaderboards",
        available="yes",
        wired="partial",
        serving="leakage_blocked",
        freeze_surface="recorded_states observation only",
        notes="Never the primary train or serve target.",
    ),
)


def feature_matrix(*, sport: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in FEATURE_MATRIX:
        if sport is not None and sport not in row.sports:
            continue
        rows.append(asdict(row))
    return rows


def unused_gold(*, sport: str | None = None) -> list[dict[str, Any]]:
    return [row for row in feature_matrix(sport=sport) if row.get("unused_gold")]


def matrix_document() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "vocabulary": {
            "available": "source can supply the signal",
            "wired": "persist path into a freeze-readable store",
            "serving": "freeze path consumes it for score or optimize",
        },
        "features": feature_matrix(),
        "unused_gold": unused_gold(),
        "issue": 583,
    }
