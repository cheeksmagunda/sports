"""Identity alias reconciliation + schedule helper smoke (offline)."""

from __future__ import annotations

from pathlib import Path

from nfl_oracle.calendar.schedule import (
    build_gameday_week_index,
    load_schedules_csv,
    research_schedule_summary,
    schedule_coverage_census,
    summarize_season_slate,
    try_load_schedules_csv,
    week_for_gameday,
)
from nfl_oracle.data.catalog import load_season_game_catalog
from nfl_oracle.identity.aliases import (
    apply_alias_table,
    reconcile_alias_collisions,
    upsert_with_aliases,
)
from nfl_oracle.identity.load import load_identity_map_from_players_file, research_identity_summary
from nfl_oracle.identity.map import IdentityMap, IdentityRecord

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
OFFLINE = FIXTURES / "offline_research"


def test_try_load_missing_schedule_returns_empty() -> None:
    assert try_load_schedules_csv(FIXTURES / "schedule" / "nope.csv") == []


def test_schedule_coverage_census_continuous() -> None:
    catalog = load_season_game_catalog(FIXTURES / "coverage" / "dense_catalog.json")
    games = load_schedules_csv(FIXTURES / "schedule" / "dense_schedules.csv")
    joined = schedule_coverage_census(catalog_seasons=catalog.to_json_obj(), games=games)
    assert joined["contest_entry"] is False
    assert joined["continuous_regular_season_count"] >= 3
    assert joined["game_count"] >= 1000


def test_gameday_index_lookup() -> None:
    games = load_schedules_csv(FIXTURES / "schedule" / "dense_schedules.csv")
    index = build_gameday_week_index(games)
    day = next(g.gameday for g in games if g.gameday is not None and g.week == 1)
    assert week_for_gameday(games, day, index=index) == 1
    assert len(index) >= 100


def test_research_schedule_summary_offline_root() -> None:
    summary = research_schedule_summary(project_root=OFFLINE, catalog_seed_count=70)
    assert summary["path_exists"] is True
    assert summary["density"]["season_count"] >= 8
    assert summary["continuous_regular_season_count"] >= 3
    assert summary["contest_entry"] is False


def test_summarize_season_slate_recent() -> None:
    games = load_schedules_csv(FIXTURES / "schedule" / "dense_schedules.csv")
    census = summarize_season_slate(games, 2024)
    assert census.continuous_regular_slate is True
    assert census.missing_regular_weeks == []


def test_identity_aliases_and_collisions() -> None:
    path = FIXTURES / "identity" / "dense_players.json"
    ident = load_identity_map_from_players_file(path)
    assert len(ident) >= 100
    dens_summary = research_identity_summary(players_path=path)
    assert dens_summary["density"]["n_with_external_alias"] >= 50
    assert dens_summary["aliases"]["display_name_collision_count"] >= 1
    assert dens_summary["aliases"]["normalized_name_collision_count"] >= 1
    assert dens_summary["aliases"]["alias_collision_count"] >= 1
    report = reconcile_alias_collisions(ident)
    assert report["n_with_external_alias"] >= 50
    assert report["display_name_collision_count"] >= 1
    assert report["normalized_name_collision_count"] >= 1
    assert report["alias_collision_count"] >= 1

    blank = IdentityMap()
    upsert_with_aliases(
        blank,
        IdentityRecord(real_player_id=1, display_name="A", external_ids={"gsis": "x"}),
    )
    upsert_with_aliases(
        blank,
        IdentityRecord(real_player_id=1, display_name="B", external_ids={"espn": "y"}),
    )
    rec = blank.get(1)
    assert rec is not None
    assert rec.display_name == "A"
    assert rec.external_ids["gsis"] == "x"
    assert rec.external_ids["espn"] == "y"
    n = apply_alias_table(
        blank,
        [
            {
                "real_player_id": 2,
                "display_name": "C",
                "gsis_id": "z",
                "position": "QB",
                "team_id": 9,
            }
        ],
    )
    assert n == 1
    assert blank.get(2) is not None
