"""Offline nflverse schedule CSV parse + density."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from nfl_oracle.calendar.schedule import (
    ScheduledGame,
    catalog_vs_schedule_density,
    earliest_upcoming_kickoff,
    games_in_week,
    load_schedules_csv,
    parse_schedules_csv,
    scheduled_kickoff_at,
    summarize_schedule_density,
    week_for_gameday,
    weeks_for_season,
)
from nfl_oracle.calendar.season import season_week_for_date
from nfl_oracle.data.catalog import load_season_game_catalog

SAMPLE = """season,week,game_id,gameday,home_team,away_team,game_type
2024,1,2024_01_AAA_BBB,2024-09-08,AAA,BBB,REG
2024,1,2024_01_CCC_DDD,2024-09-09,CCC,DDD,REG
2024,2,2024_02_AAA_CCC,2024-09-15,AAA,CCC,REG
2023,1,2023_01_XXX_YYY,2023-09-10,XXX,YYY,REG
"""

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_parse_schedules_filters_season() -> None:
    games = parse_schedules_csv(SAMPLE, season=2024)
    assert len(games) == 3
    assert weeks_for_season(games) == [1, 2]
    assert games[0].home_team == "AAA"


def test_parse_schedules_reads_gametime_column() -> None:
    sample = SAMPLE.replace(
        "season,week,game_id,gameday,home_team,away_team,game_type",
        "season,week,game_id,gameday,home_team,away_team,game_type,gametime",
    ).replace(
        "2024,1,2024_01_AAA_BBB,2024-09-08,AAA,BBB,REG",
        "2024,1,2024_01_AAA_BBB,2024-09-08,AAA,BBB,REG,13:00",
    )
    games = parse_schedules_csv(sample, season=2024)
    assert games[0].gametime == "13:00"
    # Rows this fixture didn't add a time to stay unresolved, not "00:00".
    assert games[1].gametime is None


def test_scheduled_kickoff_at_converts_et_to_utc_across_dst() -> None:
    # 2024-09-08 13:00 ET is EDT (UTC-4): 17:00Z.
    summer = ScheduledGame(
        season=2024,
        week=1,
        game_id="a",
        gameday=date(2024, 9, 8),
        home_team="AAA",
        away_team="BBB",
        gametime="13:00",
    )
    assert scheduled_kickoff_at(summer) == datetime(2024, 9, 8, 17, 0, tzinfo=UTC)

    # 2024-12-08 13:00 ET is EST (UTC-5): 18:00Z.
    winter = ScheduledGame(
        season=2024,
        week=14,
        game_id="b",
        gameday=date(2024, 12, 8),
        home_team="AAA",
        away_team="BBB",
        gametime="13:00",
    )
    assert scheduled_kickoff_at(winter) == datetime(2024, 12, 8, 18, 0, tzinfo=UTC)


def test_scheduled_kickoff_at_returns_none_when_unresolvable() -> None:
    no_time = ScheduledGame(
        season=2024,
        week=1,
        game_id="a",
        gameday=date(2024, 9, 8),
        home_team="AAA",
        away_team="BBB",
        gametime=None,
    )
    no_date = ScheduledGame(
        season=2024,
        week=1,
        game_id="a",
        gameday=None,
        home_team="AAA",
        away_team="BBB",
        gametime="13:00",
    )
    malformed = ScheduledGame(
        season=2024,
        week=1,
        game_id="a",
        gameday=date(2024, 9, 8),
        home_team="AAA",
        away_team="BBB",
        gametime="not-a-time",
    )
    assert scheduled_kickoff_at(no_time) is None
    assert scheduled_kickoff_at(no_date) is None
    assert scheduled_kickoff_at(malformed) is None


def test_earliest_upcoming_kickoff_picks_soonest_future_game() -> None:
    now = datetime(2024, 9, 8, 12, 0, tzinfo=UTC)
    past = ScheduledGame(
        season=2024,
        week=1,
        game_id="past",
        gameday=date(2024, 9, 1),
        home_team="AAA",
        away_team="BBB",
        gametime="13:00",
    )
    soon = ScheduledGame(
        season=2024,
        week=1,
        game_id="soon",
        gameday=date(2024, 9, 8),
        home_team="CCC",
        away_team="DDD",
        gametime="13:00",
    )
    later = ScheduledGame(
        season=2024,
        week=2,
        game_id="later",
        gameday=date(2024, 9, 15),
        home_team="EEE",
        away_team="FFF",
        gametime="13:00",
    )
    unresolvable = ScheduledGame(
        season=2024,
        week=1,
        game_id="unresolvable",
        gameday=date(2024, 9, 7),
        home_team="GGG",
        away_team="HHH",
        gametime=None,
    )
    found = earliest_upcoming_kickoff([past, unresolvable, later, soon], now=now)
    assert found is not None
    gameday, kickoff_at = found
    assert gameday == date(2024, 9, 8)
    assert kickoff_at == datetime(2024, 9, 8, 17, 0, tzinfo=UTC)


def test_earliest_upcoming_kickoff_correct_when_utc_date_has_rolled_but_et_has_not() -> None:
    # Sunday Night Football: gameday is Sunday (ET), 20:15 ET kickoff is
    # 00:15Z Monday (EDT, UTC-4). "now" below is Monday 00:05Z -- already
    # the next UTC calendar day, but still Sunday 20:05 ET, ten minutes
    # before kickoff and well past the T-40 due point (23:35Z Sunday).
    # Comparing `gameday` against a UTC `now.date()` would wrongly treat
    # this game as already past and skip it, leaving only the far-future
    # Thursday game below as "best" -- reporting "not due" while the real
    # next kickoff is ten minutes away. This must pick the Sunday game.
    now = datetime(2026, 9, 21, 0, 5, tzinfo=UTC)
    sunday_night = ScheduledGame(
        season=2026,
        week=3,
        game_id="snf",
        gameday=date(2026, 9, 20),
        home_team="AAA",
        away_team="BBB",
        gametime="20:15",
    )
    next_thursday = ScheduledGame(
        season=2026,
        week=4,
        game_id="tnf",
        gameday=date(2026, 9, 24),
        home_team="CCC",
        away_team="DDD",
        gametime="20:15",
    )
    found = earliest_upcoming_kickoff([next_thursday, sunday_night], now=now)
    assert found is not None
    gameday, kickoff_at = found
    assert gameday == date(2026, 9, 20)
    assert kickoff_at == datetime(2026, 9, 21, 0, 15, tzinfo=UTC)


def test_earliest_upcoming_kickoff_none_when_nothing_resolvable() -> None:
    now = datetime(2024, 9, 8, 12, 0, tzinfo=UTC)
    unresolvable = ScheduledGame(
        season=2024,
        week=1,
        game_id="unresolvable",
        gameday=date(2024, 9, 9),
        home_team="GGG",
        away_team="HHH",
        gametime=None,
    )
    assert earliest_upcoming_kickoff([unresolvable], now=now) is None


def test_parse_skips_malformed_and_nonpositive_weeks() -> None:
    messy = """season,week,game_id,gameday,home_team,away_team,game_type
nope,1,x,2024-09-01,A,B,REG
2024,bad,x,2024-09-01,A,B,REG
2024,0,x,2024-09-01,A,B,REG
2024,1,ok,not-a-date,A,B,REG
2024,1,ok2,,A,B,REG
2024,1,pre,2024-08-01,A,B,PRE
"""
    games = parse_schedules_csv(messy)
    assert len(games) == 2
    assert games[0].gameday is None
    assert games[1].gameday is None


def test_dense_schedule_fixture_density() -> None:
    path = FIXTURES / "schedule" / "dense_schedules.csv"
    games = load_schedules_csv(path)
    dens = summarize_schedule_density(games)
    assert dens.season_count >= 8
    assert dens.game_count >= 2000  # continuous REG+POST for 2018-2025
    assert dens.week_count >= 140
    assert dens.min_games_per_season is not None
    assert dens.max_games_per_season is not None
    assert dens.min_games_per_season <= dens.max_games_per_season
    assert dens.team_count >= 30
    assert dens.missing_gameday_count == 0
    assert "2024" in dens.weeks_by_season
    assert dens.weeks_by_season["2024"][:5] == [1, 2, 3, 4, 5]
    dumped = dens.to_dict()
    assert dumped["game_count"] == dens.game_count


def test_week_lookup_and_season_week_from_schedule() -> None:
    games = load_schedules_csv(FIXTURES / "schedule" / "dense_schedules.csv")
    assert week_for_gameday(games, date(2024, 9, 5)) == 1
    assert week_for_gameday(games, date(2020, 1, 1)) is None
    week1 = games_in_week(games, season=2024, week=1)
    assert len(week1) >= 14
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
    assert cmp["catalog_seed_count"] == 70
    assert cmp["schedule_game_count"] == dens.game_count
    assert cmp["contest_entry"] is False
    # Continuous slate is denser than seed anchors.
    assert cmp["seed_to_schedule_ratio"] < 1.0
    assert cmp["schedule_games_beyond_seeds"] > 0
