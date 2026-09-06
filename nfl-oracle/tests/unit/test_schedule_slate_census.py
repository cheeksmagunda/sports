"""Continuous season slate discovery + coverage census (offline nflverse)."""

from __future__ import annotations

from pathlib import Path

from nfl_oracle.calendar.schedule import (
    build_gameday_week_index,
    games_for_season,
    load_schedules_csv,
    research_schedule_summary,
    resolve_schedule_csv_path,
    schedule_coverage_census,
    summarize_season_slate,
    try_load_schedules_csv,
)
from nfl_oracle.data.catalog import load_season_game_catalog
from nfl_oracle.data.paths import resolve_data_paths
from nfl_oracle.data.summary import research_data_summary

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
OFFLINE = FIXTURES / "offline_research"


def test_continuous_regular_slate_for_recent_seasons() -> None:
    games = load_schedules_csv(FIXTURES / "schedule" / "dense_schedules.csv")
    for season in (2022, 2023, 2024):
        census = summarize_season_slate(games, season)
        assert census.continuous_regular_slate is True
        assert census.missing_regular_weeks == []
        assert census.regular_weeks[0] == 1
        assert len(census.regular_weeks) >= 17
        assert census.regular_season_game_count >= 256
        assert census.game_count >= census.regular_season_game_count
        slate = games_for_season(games, season, game_types=("REG",))
        assert len(slate) == census.regular_season_game_count


def test_schedule_coverage_census_vs_dense_catalog() -> None:
    catalog = load_season_game_catalog(FIXTURES / "coverage" / "dense_catalog.json")
    games = load_schedules_csv(FIXTURES / "schedule" / "dense_schedules.csv")
    census = schedule_coverage_census(
        catalog_seasons=catalog.to_json_obj(),
        games=games,
    )
    assert census["contest_entry"] is False
    assert census["continuous_regular_season_count"] >= 3
    row_2024 = census["seasons"]["2024"]
    assert row_2024["continuous_regular_slate"] is True
    assert row_2024["schedule_games_beyond_seeds"] > 0
    assert row_2024["catalog_seed_count"] >= 4


def test_resolve_and_try_load_under_offline_research_root() -> None:
    paths = resolve_data_paths(OFFLINE)
    resolved = resolve_schedule_csv_path(paths.root)
    assert resolved is not None
    assert resolved.name == "schedules.csv"
    games = try_load_schedules_csv(resolved)
    assert len(games) >= 6000
    assert try_load_schedules_csv(None) == []
    assert try_load_schedules_csv(paths.root / "missing.csv") == []
    index = build_gameday_week_index(games)
    assert len(index) >= 1000


def test_research_schedule_summary_includes_census() -> None:
    catalog = load_season_game_catalog(OFFLINE / "data" / "catalog" / "season_game_ids.json")
    seasons = catalog.to_json_obj()
    seed_total = sum(len(v) for v in seasons.values())
    summary = research_schedule_summary(
        project_root=OFFLINE,
        catalog_seed_count=seed_total,
        catalog_seasons=seasons,
    )
    assert summary["contest_entry"] is False
    assert summary["density"]["season_count"] >= 20
    assert summary["density"]["game_count"] >= 6000
    assert summary["continuous_regular_season_count"] >= 20
    assert summary["vs_catalog"]["schedule_games_beyond_seeds"] > 0
    assert "2024" in summary["slate_samples"]
    assert summary["slate_samples"]["2024"]["continuous_regular_slate"] is True
    assert summary["coverage_census"]["continuous_regular_season_count"] >= 3
    assert summary["attribution"]["license"] == "CC BY 4.0"


def test_research_data_summary_embeds_schedule_census() -> None:
    payload = research_data_summary(project_root=OFFLINE)
    assert payload["contest_entry"] is False
    sched = payload["schedule"]
    assert sched["density"]["season_count"] >= 20
    assert sched["continuous_regular_season_ratio"] >= 0.8
    assert payload["coverage_matrix"]["alignment"]["aligned_season_count"] >= 1
