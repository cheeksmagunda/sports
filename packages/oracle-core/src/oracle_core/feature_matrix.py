"""Portfolio FEATURE_MATRIX: available | wired | serving (#583).

Vocabulary (orthogonal to rs_field_map mapped/gap/leakage)::

  - available: provider or external source can supply the signal today
  - wired: ingest / fuse / context code persists it into a freeze-readable store
  - serving: freeze path consumes it for predictions or optimizer scoring
    (non-zero effect possible under current defaults / knobs)

UNUSED_GOLD = available and (not wired or not serving), excluding
leakage-blocked / forbidden train targets.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

SCHEMA_VERSION = 1

Sport = Literal["wnba", "nfl", "nba", "nhl", "portfolio"]
PathStatus = Literal["yes", "no", "partial", "leakage_blocked", "label_only"]


@dataclass(frozen=True)
class FeatureRow:
    """One Real Sports or external signal in the freeze-relevant inventory."""

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
        freeze_surface="NFL ridge/valuelaw priors + HV grade labels",
        notes="Primary Real value label; WNBA uses nba_api + RS boxes into game_logs.",
    ),
    FeatureRow(
        feature="Corpus C contest / draftStats HV",
        sports=("wnba", "nfl", "nba", "nhl"),
        source="draftStats.highestBoostedValuePlayers",
        available="yes",
        wired="yes",
        serving="label_only",
        freeze_surface="train/grade Total Value boards; not a live feature",
        notes="NBA/NHL durable HV corpus still thin; never winning drafts.",
    ),
    FeatureRow(
        feature="draftStats.popularPlayers / mostCommon3x / mostDrafted",
        sports=("wnba", "nfl"),
        source="Daily Draft Stats non-HV sections",
        available="yes",
        wired="partial",
        serving="no",
        freeze_surface="recorded_states / slate_labels only",
        notes="WNBA MAX(drafts) may include section drafts if present; not a distinct model term.",
        unused_gold=True,
    ),
    FeatureRow(
        feature="card_boost / multiplierBonus",
        sports=("wnba", "nfl", "nhl"),
        source="RS pool pre-lock",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="WNBA EB boost_beta + picker; NFL optimizer score",
        notes="NHL early-slate often all-zero until every franchise has 1 GP.",
    ),
    FeatureRow(
        feature="vegas_total / vegas_spread",
        sports=("wnba",),
        source="The Odds API",
        available="yes",
        wired="yes",
        serving="partial",
        freeze_surface="EB vegas_total term; spread → game_script multiplier",
        notes="implied_team_total classified eb_vegas but EB predict uses vegas_total only.",
        unused_gold=True,
    ),
    FeatureRow(
        feature="h2h moneyline → team_moneyline",
        sports=("wnba", "nfl"),
        source="Odds API (WNBA) / RS game (NFL)",
        available="yes",
        wired="yes",
        serving="partial",
        freeze_surface="NFL ridge REQUIRED_RS_POOL; WNBA EB moneyline_beta when fused",
        notes=(
            "WNBA job1 #583 wires h2h into team_to_vegas + fuse. Serving needs "
            "merge+redeploy+job1 and a non-zero moneyline_beta on the EB artifact."
        ),
        unused_gold=True,
    ),
    FeatureRow(
        feature="overallRank / injuryBodyPart",
        sports=("wnba", "nfl"),
        source="RS pool cards",
        available="yes",
        wired="yes",
        serving="partial",
        freeze_surface="NFL ridge context; WNBA EB overall_rank_beta when fused",
        notes="WNBA job1 already fuses rank/body into head_features (#523).",
    ),
    FeatureRow(
        feature="RotoWire starters / is_confirmed_starter",
        sports=("wnba",),
        source="RotoWire free page",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="serve _starter_multiplier on EB / ladder",
        notes="Advisory rotowire_empty until ~13:00Z tip-day job1; 30h near-tip gate.",
    ),
    FeatureRow(
        feature="team_pace / opp_pace / game_pace_implied",
        sports=("wnba", "nfl"),
        source="rolling game_logs / Corpus G",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="WNBA EB pace betas; NFL REQUIRED_SLATE_CONTEXT pace priors",
        notes="",
    ),
    FeatureRow(
        feature="ridge / EB slate context bank",
        sports=("wnba", "nfl"),
        source="matchup + kickoff_slot + injury_* + weather_*",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="NFL RatingModel force-include; WNBA head_features + EB",
        notes="NFL weather gated by NWS capture; indoor → available=false.",
    ),
    FeatureRow(
        feature="live / measured ownership (drafts)",
        sports=("wnba", "nfl"),
        source="RS draftStats drafts + LIVE_OWNERSHIP_CAPTURE",
        available="yes",
        wired="yes",
        serving="partial",
        freeze_surface="field measured path + max_value ownership fade",
        notes=(
            "Pregame draftStats often empty; LIVE capture window T-30. "
            "Post-lock same-slate drafts are leakage-blocked for train features."
        ),
        unused_gold=True,
    ),
    FeatureRow(
        feature="prop_points_over_prob (D78)",
        sports=("wnba",),
        source="Odds API player props",
        available="yes",
        wired="yes",
        serving="no",
        freeze_surface="_prop_signal_multiplier when PROP_SIGNAL_SCALE>0",
        notes=(
            "Code default scale=0.0; EXPECTED_PROD_CONFIG wants 0.3. "
            "Do not flip near freeze without placement calibration."
        ),
        unused_gold=True,
    ),
    FeatureRow(
        feature="seasonAverages.*",
        sports=("wnba", "nfl"),
        source="RS feed / pool",
        available="yes",
        wired="no",
        serving="no",
        freeze_surface="extract_season_averages exists; not called on freeze path",
        notes="Falsely marked mapped in some rs_field_map rows before #583.",
        unused_gold=True,
    ),
    FeatureRow(
        feature="gameTeamComparison.previousMeetings / standings extras",
        sports=("nfl",),
        source="Corpus G stats",
        available="yes",
        wired="no",
        serving="no",
        freeze_surface="corpus dump only; lastTenWins is the wired standings leaf",
        notes="",
        unused_gold=True,
    ),
    FeatureRow(
        feature="contest_leaderboards winning drafts",
        sports=("wnba", "nfl"),
        source="RS leaderboards",
        available="yes",
        wired="partial",
        serving="leakage_blocked",
        freeze_surface="recorded_states observation only",
        notes="Never primary train/serve target.",
    ),
    FeatureRow(
        feature="injury_cascade + game_script_minutes",
        sports=("wnba",),
        source="pool OUT + vegas spread/total",
        available="yes",
        wired="yes",
        serving="yes",
        freeze_surface="job2 minutes redistribution + game_script multiplier",
        notes="game_script_minutes_enabled expected True in prod.",
    ),
)


def feature_matrix(*, sport: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in FEATURE_MATRIX:
        if sport is not None and sport not in row.sports and "portfolio" not in row.sports:
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
            "wired": "persist path into freeze-readable store",
            "serving": "freeze path consumes for score / optimize",
        },
        "features": feature_matrix(),
        "unused_gold": unused_gold(),
        "issue": 583,
    }
