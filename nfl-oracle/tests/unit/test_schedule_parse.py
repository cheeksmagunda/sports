"""Offline nflverse schedule CSV parse."""

from __future__ import annotations

from nfl_oracle.calendar.schedule import parse_schedules_csv, weeks_for_season

SAMPLE = """season,week,game_id,gameday,home_team,away_team
2024,1,2024_01_AAA_BBB,2024-09-08,AAA,BBB
2024,1,2024_01_CCC_DDD,2024-09-09,CCC,DDD
2024,2,2024_02_AAA_CCC,2024-09-15,AAA,CCC
2023,1,2023_01_XXX_YYY,2023-09-10,XXX,YYY
"""


def test_parse_schedules_filters_season() -> None:
    games = parse_schedules_csv(SAMPLE, season=2024)
    assert len(games) == 3
    assert weeks_for_season(games) == [1, 2]
    assert games[0].home_team == "AAA"
