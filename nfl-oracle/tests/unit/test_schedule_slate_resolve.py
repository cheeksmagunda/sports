"""Week/slate resolution helpers over dense offline schedules."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from nfl_oracle.calendar.schedule import load_schedules_csv, parse_schedules_csv
from nfl_oracle.calendar.slate import (
    opponent_for_team,
    opponents_by_team,
    research_schedule_slate,
    resolve_slate,
    resolve_slate_for_date,
    resolve_slate_for_season_week,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
DENSE = FIXTURES / "schedule" / "dense_schedules.csv"
OFFLINE = FIXTURES / "offline_research"

SAMPLE = """season,week,game_id,gameday,home_team,away_team,game_type
2024,1,2024_01_AAA_BBB,2024-09-05,AAA,BBB,REG
2024,1,2024_01_CCC_DDD,2024-09-08,CCC,DDD,REG
2024,2,2024_02_AAA_CCC,2024-09-15,AAA,CCC,REG
"""


def test_resolve_slate_season_week_returns_games_and_opponents() -> None:
    games = parse_schedules_csv(SAMPLE)
    slate = resolve_slate_for_season_week(games, season=2024, week=1)
    assert slate.resolved is True
    assert slate.resolve_mode == "season_week"
    assert slate.season == 2024
    assert slate.week == 1
    assert len(slate.games) == 2
    assert slate.opponents["AAA"] == "BBB"
    assert slate.opponents["BBB"] == "AAA"
    assert opponent_for_team(slate.games, "ccc") == "DDD"
    payload = slate.to_dict()
    assert payload["contest_entry"] is False
    assert payload["game_count"] == 2
    assert payload["games"][0]["opponent_home"] == "BBB"


def test_resolve_slate_for_date_exact_and_span() -> None:
    games = parse_schedules_csv(SAMPLE)
    exact = resolve_slate_for_date(games, date(2024, 9, 5))
    assert exact.resolve_mode == "date_exact_gameday"
    assert exact.week == 1
    assert exact.resolved is True
    # Mid-window non-gameday still maps via week span
    span = resolve_slate_for_date(games, date(2024, 9, 6))
    assert span.resolve_mode == "date_week_span"
    assert span.week == 1
    assert len(span.games) == 2
    miss = resolve_slate_for_date(games, date(2024, 9, 11))
    assert miss.resolve_mode == "unresolved"
    assert miss.week is None
    assert miss.games == ()


def test_resolve_slate_unified_and_empty_week() -> None:
    games = parse_schedules_csv(SAMPLE)
    by_sw = resolve_slate(games, season=2024, week=2)
    assert by_sw.week == 2
    assert by_sw.opponents["AAA"] == "CCC"
    empty = resolve_slate(games, season=2024, week=99)
    assert empty.resolved is False
    assert empty.note == "no_games_for_season_week"
    none = resolve_slate(games)
    assert none.note == "season_week_or_date_required"


def test_dense_fixture_week1_2024_opponents() -> None:
    games = load_schedules_csv(DENSE)
    slate = resolve_slate(games, season=2024, week=1)
    assert slate.resolved is True
    assert len(slate.games) >= 14
    assert opponents_by_team(slate.games)["KC"] == "BAL"
    by_date = resolve_slate_for_date(games, date(2024, 9, 5))
    assert by_date.week == 1
    assert by_date.resolve_mode == "date_exact_gameday"


def test_research_schedule_slate_offline_root() -> None:
    payload = research_schedule_slate(project_root=OFFLINE, season=2024, week=1)
    assert payload["contest_entry"] is False
    assert payload["resolved"] is True
    assert payload["game_count"] >= 14
    assert "KC" in payload["opponents"]
    with_team = research_schedule_slate(
        project_root=OFFLINE,
        day=date(2024, 9, 5),
        team="kc",
    )
    assert with_team["team_on_slate"] is True
    assert with_team["team_opponent"] == "BAL"
    assert with_team["resolve_mode"] == "date_exact_gameday"
