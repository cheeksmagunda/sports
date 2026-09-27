from __future__ import annotations

from nhl_oracle.history_loader import (
    _coverage_row,
    flatten_boxscore_player_rows,
    season_code_for_start_year,
    season_start_year_from_code,
)


def test_season_code_round_trip() -> None:
    assert season_code_for_start_year(2024) == 20242025
    assert season_start_year_from_code(20242025) == 2024


def test_flatten_boxscore_player_rows_keeps_home_away_and_goalie_fields() -> None:
    boxscore = {
        "id": 2024020001,
        "season": 20242025,
        "gameType": 2,
        "gameDate": "2024-10-04",
        "awayTeam": {"id": 1, "abbrev": "AWY", "score": 2},
        "homeTeam": {"id": 2, "abbrev": "HOM", "score": 4},
        "playerByGameStats": {
            "awayTeam": {
                "forwards": [
                    {
                        "playerId": 10,
                        "name": {"default": "Away Skater"},
                        "position": "C",
                        "sweaterNumber": 9,
                        "goals": 1,
                        "assists": 1,
                        "points": 2,
                        "sog": 3,
                        "hits": 1,
                        "blockedShots": 0,
                        "pim": 0,
                        "plusMinus": -1,
                        "giveaways": 2,
                        "takeaways": 1,
                        "shifts": 18,
                        "toi": "16:32",
                        "powerPlayGoals": 1,
                        "faceoffWinningPctg": 52.4,
                    }
                ],
                "defense": [],
                "goalies": [
                    {
                        "playerId": 30,
                        "name": {"default": "Away Goalie"},
                        "position": "G",
                        "sweaterNumber": 30,
                        "shotsAgainst": 35,
                        "saves": 31,
                        "goalsAgainst": 4,
                        "savePctg": 0.885714,
                        "starter": True,
                        "decision": "L",
                        "toi": "58:51",
                    }
                ],
            },
            "homeTeam": {
                "forwards": [
                    {
                        "playerId": 20,
                        "name": {"default": "Home Skater"},
                        "position": "RW",
                        "sweaterNumber": 12,
                        "goals": 2,
                        "assists": 0,
                        "points": 2,
                        "sog": 5,
                    }
                ],
                "defense": [],
                "goalies": [],
            },
        },
    }
    rows = flatten_boxscore_player_rows(
        boxscore,
        fetched_at="2026-09-27T00:00:00Z",
        source_url="https://example.invalid/gamecenter/2024020001/boxscore",
    )
    assert len(rows) == 3
    away_skater = next(row for row in rows if row["player_id"] == 10)
    away_goalie = next(row for row in rows if row["player_id"] == 30)
    home_skater = next(row for row in rows if row["player_id"] == 20)
    assert away_skater["is_home"] is False
    assert away_skater["team_id"] == 1
    assert away_skater["opponent_team_id"] == 2
    assert away_skater["faceoff_winning_pctg"] == 52.4
    assert away_goalie["position"] == "G"
    assert away_goalie["shots_against"] == 35
    assert away_goalie["save_pctg"] == 0.885714
    assert away_goalie["decision"] == "L"
    assert home_skater["is_home"] is True
    assert home_skater["team_id"] == 2


def test_coverage_row_reports_complete_only_when_everything_loaded() -> None:
    full = _coverage_row(
        season_start_year=2024,
        season_code=20242025,
        game_types=(2, 3),
        scheduled_games=1417,
        loaded_games=1417,
        loaded_player_rows=54000,
        failed_games=0,
        first_game_date="2024-10-04",
        last_game_date="2025-06-17",
    )
    partial = _coverage_row(
        season_start_year=2025,
        season_code=20252026,
        game_types=(2,),
        scheduled_games=1312,
        loaded_games=1300,
        loaded_player_rows=50000,
        failed_games=12,
        first_game_date="2025-10-07",
        last_game_date="2026-04-18",
    )
    assert full.status == "complete"
    assert partial.status == "partial"
    assert partial.game_types == "2"
