"""Offline nflverse schedule CSV parse + density."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from nfl_oracle.calendar.schedule import (
    catalog_vs_schedule_density,
    games_in_week,
    load_schedules_csv,
    parse_schedules_csv,
    summarize_schedule_density,
    week_for_gameday,
    weeks_for_season,
)
from nfl_oracle.calendar.season import season_week_for_date
from nfl_oracle.data.catalog import load_season_game_catalog

SAMPLE = """season,week,game_id,gameday,home_team,away_team
2024,1,2024_01_AAA_BBB,2024-09-08,AAA,BBB
2024,1,2024_01_CCC_DDD,2024-09-09,CCC,DDD
2024,2,2024_02_AAA_CCC,2024-09-15,AAA,CCC
2023,1,2023_01_XXX_YYY,2023-09-10,XXX,YYY
"""

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_parse_schedules_filters_season() -> None:
    games = parse_schedules_csv(SAMPLE, season=2024)
    assert len(games) == 3
    assert weeks_for_season(games) == [1, 2]
    assert games[0].home_team == "AAA"


def test_parse_skips_malformed_and_nonpositive_weeks() -> None:
    messy = """season,week,game_id,gameday,home_team,away_team
nope,1,x,2024-09-01,A,B
2024,bad,x,2024-09-01,A,B
2024,0,x,2024-09-01,A,B
2024,1,ok,not-a-date,A,B
2024,1,ok2,,A,B
"""
    games = parse_schedules_csv(messy)
    assert len(games) == 2
    assert games[0].gameday is None
    assert games[1].gameday is None


def test_dense_schedule_fixture_density() -> None:
    path = FIXTURES / "schedule" / "dense_schedules.csv"
    games = load_schedules_csv(path)
    dens = summarize_schedule_density(games)
    assert dens.season_count == 4
    assert dens.game_count >= 36
    assert dens.week_count >= 12
    assert dens.min_games_per_season is not None
    assert dens.max_games_per_season is not None
    assert dens.min_games_per_season <= dens.max_games_per_season
    assert dens.team_count >= 20
    assert dens.missing_gameday_count >= 1
    assert "2024" in dens.weeks_by_season
    assert 1 in dens.weeks_by_season["2024"]
    dumped = dens.to_dict()
    assert dumped["game_count"] == dens.game_count


def test_week_lookup_and_season_week_from_schedule() -> None:
    games = load_schedules_csv(FIXTURES / "schedule" / "dense_schedules.csv")
    assert week_for_gameday(games, date(2024, 9, 5)) == 1
    assert week_for_gameday(games, date(2020, 1, 1)) is None
    week1 = games_in_week(games, season=2024, week=1)
    assert len(week1) >= 3
    resolved = season_week_for_date(date(2024, 9, 5), schedule=games)
    assert resolved.season == 2024
    assert resolved.week == 1
    assert resolved.note == "week_from_schedule"
    unresolved = season_week_for_date(date(2024, 9, 5))
    assert unresolved.week is None
    assert "unresolved" in unresolved.note


def test_catalog_vs_schedule_density_with_dense_fixtures() -> None:
    catalog = load_season_game_catalog(FIXTURES / "coverage" / "dense_catalog.json")
    games = load_schedules_csv(FIXTURES / "schedule" / "dense_schedules.csv")
    dens = summarize_schedule_density(games)
    seed_total = sum(len(v) for v in catalog.seasons.values())
    cmp = catalog_vs_schedule_density(
        catalog_seed_count=seed_total,
        schedule_game_count=dens.game_count,
    )
    assert cmp["catalog_seed_count"] == 56
    assert cmp["schedule_game_count"] == dens.game_count
    assert cmp["contest_entry"] is False
    assert cmp["seed_to_schedule_ratio"] > 1.0  # seeds denser than small schedule fixture
