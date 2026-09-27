"""Daily Draft Stats / draftStats section inventory (issue #526).

Enumerates every ``sectionName`` and player-row field observed in Real Sports
fixtures and sport-app parsers. This is a durable catalog for the separate
corpus layout (``recorded_states/``, ``total_value_leaderboards/``). It does
not scrape the network and does not mint credentials.

Sources (code + fixtures; no live secrets)::

  - WNBA ``wnba_oracle.ingest.contest_stats.DRAFT_STATS_SECTIONS``
  - WNBA supplemental ``leaderboard_lineup`` (from contest_leaderboards, not a
    provider draftStats sectionName)
  - NFL ``nfl_oracle.contests.parse.parse_draft_stats`` + dayclose fixtures
    (``mostDrafted``, ``highestBoostedValuePlayers``)
  - NHL discovery fixtures (anonymous draftStats sections without sectionName)
  - WNBA results API tests (``mostValuablePlayers`` as a multi-section label)

Train / grade labels remain Highest-value boards only
(``highestBoostedValuePlayers``). Other sections and finisher lineups are
recorded_states / observations, never primary train targets.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

SCHEMA_VERSION = 1

# Provider Daily Draft Stats title (displayInfo.title on /stats payloads).
DAILY_DRAFT_STATS_TITLE = "Daily Draft Stats"

# Total Value / Highest value board — the only train/grade label section.
HV_SECTION = "highestBoostedValuePlayers"

SectionKind = Literal[
    "provider_draft_stats",
    "synthetic_supplemental",
    "fixture_or_test_only",
]


@dataclass(frozen=True)
class DraftStatsSection:
    """One named Daily Draft Stats (or derived) section."""

    name: str
    kind: SectionKind
    sports: tuple[str, ...]
    description: str
    train_label: bool
    # Where durable WNBA rows land today (Postgres) when applicable.
    wnba_store: str | None = None


@dataclass(frozen=True)
class FieldSpec:
    """One field on a draftStats player row or nested object."""

    path: str
    description: str
    sports: tuple[str, ...]


# Canonical section inventory. Extend when unknown_sections logs fire.
DRAFT_STATS_SECTIONS: tuple[DraftStatsSection, ...] = (
    DraftStatsSection(
        name="highestBoostedValuePlayers",
        kind="provider_draft_stats",
        sports=("wnba", "nfl", "nba", "nhl"),
        description=(
            "Highest value / Total Value Daily Leaderboard "
            "(Real Sports Daily Draft Stats)."
        ),
        train_label=True,
        wnba_store="slate_labels",
    ),
    DraftStatsSection(
        name="popularPlayers",
        kind="provider_draft_stats",
        sports=("wnba",),
        description="Community popular / most-drafted community board.",
        train_label=False,
        wnba_store="slate_labels",
    ),
    DraftStatsSection(
        name="mostCommon3xPlayers",
        kind="provider_draft_stats",
        sports=("wnba",),
        description="Players most often drafted at the 3x (or equivalent) slot.",
        train_label=False,
        wnba_store="slate_labels",
    ),
    DraftStatsSection(
        name="mostDrafted",
        kind="provider_draft_stats",
        sports=("nfl",),
        description="NFL field popularity section seen in dayclose / Corpus C fixtures.",
        train_label=False,
        wnba_store=None,
    ),
    DraftStatsSection(
        name="leaderboard_lineup",
        kind="synthetic_supplemental",
        sports=("wnba",),
        description=(
            "WNBA D85 supplemental labels derived from contest_leaderboards "
            "lineups (not a provider draftStats sectionName)."
        ),
        train_label=False,
        wnba_store="slate_labels",
    ),
    DraftStatsSection(
        name="mostValuablePlayers",
        kind="fixture_or_test_only",
        sports=("wnba",),
        description=(
            "Appears in WNBA results-API unit fixtures as a second section label; "
            "not in DRAFT_STATS_SECTIONS ingest allowlist. Persist if live payloads "
            "ever emit it (unknown_sections log)."
        ),
        train_label=False,
        wnba_store=None,
    ),
)

# Union of player-row fields across WNBA contest_stats parse + NFL DraftStatRow.
PLAYER_ROW_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("player.id", "Platform player id (nested).", ("wnba", "nfl")),
    FieldSpec("player.displayName", "Display name.", ("wnba",)),
    FieldSpec("player.firstName", "Given name fallback.", ("wnba", "nfl")),
    FieldSpec("player.lastName", "Family name fallback.", ("wnba", "nfl")),
    FieldSpec("playerId", "Flat player id (NFL-style payloads).", ("nfl", "nhl")),
    FieldSpec("team.key", "Team abbreviation key.", ("wnba",)),
    FieldSpec("team.id", "Team id (nested).", ("nfl",)),
    FieldSpec("teamId", "Flat team id.", ("nfl",)),
    FieldSpec("multiplierBonus", "Card boost added to slot multiplier.", ("wnba", "nfl", "nhl")),
    FieldSpec(
        "value",
        "Realized per-slate Real score / value string or number.",
        ("wnba", "nfl", "nhl"),
    ),
    FieldSpec("count", "Draft count within the section (NFL).", ("nfl",)),
    FieldSpec("avgMultiplier", "Average effective multiplier.", ("nfl",)),
    FieldSpec("avgPosition", "Average slot position.", ("nfl",)),
    FieldSpec("avgScore", "Average entry score contribution.", ("nfl",)),
    FieldSpec("highestScore", "Highest observed score contribution.", ("nfl",)),
    FieldSpec("baseBoostedValue", "Base boosted value when present.", ("nfl",)),
    FieldSpec("mostCommonPosition", "Most common slot (string or int).", ("nfl",)),
    FieldSpec("countAtHighestPosition", "Count at highest slot.", ("nfl",)),
    FieldSpec("positionOfHighestScore", "Slot of highest score.", ("nfl",)),
    FieldSpec("displayStats[].label", "UI stat label (WNBA).", ("wnba",)),
    FieldSpec("displayStats[].value", "UI stat value (WNBA).", ("wnba",)),
)

# Known displayStats labels parsed by WNBA ingest.
WNBA_DISPLAY_STAT_LABELS: tuple[str, ...] = ("Drafts",)

# contest_leaderboards lineup pick shape (recorded_states observation only).
LEADERBOARD_LINEUP_PICK_FIELDS: tuple[str, ...] = (
    "order",
    "displayName",
    "playerId",
    "value",
    "multiplier",
    "multiplierBonus",
    "score",
)

# WNBA slate_labels durable columns (Postgres projection of draftStats).
SLATE_LABEL_COLUMNS: tuple[str, ...] = (
    "contest_id",
    "slate_date",
    "section",
    "platform_player_id",
    "display_name",
    "team_key",
    "card_boost",
    "drafts",
    "real_score",
    "ingested_at",
)


def provider_section_names(*, sport: str | None = None) -> tuple[str, ...]:
    """Return provider draftStats sectionNames, optionally filtered by sport."""

    names: list[str] = []
    for section in DRAFT_STATS_SECTIONS:
        if section.kind != "provider_draft_stats":
            continue
        if sport is not None and sport not in section.sports:
            continue
        names.append(section.name)
    return tuple(names)


def all_section_names() -> tuple[str, ...]:
    return tuple(section.name for section in DRAFT_STATS_SECTIONS)


def train_label_sections() -> tuple[str, ...]:
    return tuple(section.name for section in DRAFT_STATS_SECTIONS if section.train_label)


def catalog_document() -> dict[str, Any]:
    """JSON-serializable catalog for corpus ``manifest/draft_stats_sections.json``."""

    return {
        "schema_version": SCHEMA_VERSION,
        "display_info_title": DAILY_DRAFT_STATS_TITLE,
        "hv_section": HV_SECTION,
        "train_label_sections": list(train_label_sections()),
        "sections": [asdict(section) for section in DRAFT_STATS_SECTIONS],
        "player_row_fields": [asdict(field) for field in PLAYER_ROW_FIELDS],
        "wnba_display_stat_labels": list(WNBA_DISPLAY_STAT_LABELS),
        "leaderboard_lineup_pick_fields": list(LEADERBOARD_LINEUP_PICK_FIELDS),
        "slate_label_columns": list(SLATE_LABEL_COLUMNS),
        "corpus_layout": {
            "total_value_leaderboards": (
                "total_value_leaderboards/{sport}/{year}/slate_{YYYY-MM-DD}/"
                "highestBoostedValuePlayers.json"
            ),
            "recorded_states_draft_stats": (
                "recorded_states/{sport}/{year}/slate_{YYYY-MM-DD}/"
                "draft_stats_all_sections.jsonl"
            ),
            "recorded_states_lineups": (
                "recorded_states/{sport}/{year}/slate_{YYYY-MM-DD}/"
                "contest_leaderboards.json"
            ),
            "note": (
                "contest_leaderboards lineups are observations "
                "(recorded_states), never train labels."
            ),
        },
        "sources": [
            "wnba_oracle.ingest.contest_stats",
            "nfl_oracle.contests.parse.parse_draft_stats",
            "nfl-oracle/tests/unit/test_dayclose.py (mostDrafted)",
            "wnba-oracle/tests/fixtures/realsports/leaderboard_entries.json",
            "drive/nfl_fixtures/contest_2124_stats.json (Daily Draft Stats title)",
        ],
    }
