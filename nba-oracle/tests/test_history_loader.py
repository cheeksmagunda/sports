from __future__ import annotations

import pytest

from nba_oracle.history_loader import (
    _coverage_row,
    ensure_public_ssl_database_url,
    extract_schedule_games,
    flatten_gamedetail_player_rows,
    season_code_for_start_year,
    season_start_year_from_code,
)


def test_season_code_round_trip() -> None:
    assert season_code_for_start_year(2023) == 20232024
    assert season_start_year_from_code(20232024) == 2023


def test_ensure_public_ssl_rejects_internal_and_sets_sslmode() -> None:
    with pytest.raises(RuntimeError, match="railway.internal"):
        ensure_public_ssl_database_url(
            "postgresql://u:p@postgres-6eeu.railway.internal:5432/railway"
        )
    secured = ensure_public_ssl_database_url(
        "postgresql://u:p@trolley.proxy.rlwy.net:17927/railway"
    )
    assert "sslmode=require" in secured
    assert "trolley.proxy.rlwy.net" in secured


def test_extract_schedule_games_filters_final_regular_and_playoffs() -> None:
    payload = {
        "lscd": [
            {
                "mscd": {
                    "g": [
                        {"gid": "0022300001", "st": "3", "stt": "Final", "gdte": "2023-10-24"},
                        {"gid": "0012300001", "st": "3", "stt": "Final", "gdte": "2023-10-10"},
                        {"gid": "0042300101", "st": "3", "stt": "Final", "gdte": "2024-04-20"},
                        {"gid": "0022300002", "st": "1", "stt": "3:00 pm ET", "gdte": "2023-10-25"},
                    ]
                }
            }
        ]
    }
    rows = extract_schedule_games(payload, game_type_prefixes=("002", "004"))
    assert [row["gid"] for row in rows] == ["0022300001", "0042300101"]


def test_flatten_gamedetail_player_rows_keeps_home_away_box_lines() -> None:
    detail = {
        "gid": "0022300451",
        "gdte": "2024-01-01",
        "stt": "Final",
        "hls": {
            "tid": 1610612752,
            "ta": "NYK",
            "s": 112,
            "pstsg": [
                {
                    "pid": 1628384,
                    "fn": "OG",
                    "ln": "Anunoby",
                    "pos": "SF",
                    "num": "8",
                    "min": 35,
                    "sec": 2,
                    "pts": 17,
                    "reb": 6,
                    "ast": 1,
                    "stl": 2,
                    "blk": 0,
                    "tov": 1,
                    "fgm": 7,
                    "fga": 12,
                    "tpm": 3,
                    "tpa": 6,
                    "ftm": 0,
                    "fta": 0,
                    "pm": 19,
                }
            ],
        },
        "vls": {
            "tid": 1610612750,
            "ta": "MIN",
            "s": 106,
            "pstsg": [
                {
                    "pid": 1630183,
                    "fn": "Jaden",
                    "ln": "McDaniels",
                    "pos": "SF",
                    "num": "3",
                    "min": 33,
                    "sec": 18,
                    "pts": 8,
                    "reb": 1,
                    "ast": 0,
                    "stl": 1,
                    "blk": 1,
                    "tov": 1,
                    "fgm": 2,
                    "fga": 8,
                    "tpm": 1,
                    "tpa": 5,
                    "ftm": 3,
                    "fta": 4,
                    "pm": -9,
                }
            ],
        },
    }
    rows = flatten_gamedetail_player_rows(
        detail,
        season_start_year=2023,
        fetched_at="2026-09-27T00:00:00Z",
        source_url="https://example.invalid/gamedetail",
    )
    assert len(rows) == 2
    home = next(row for row in rows if row["player_id"] == 1628384)
    away = next(row for row in rows if row["player_id"] == 1630183)
    assert home["is_home"] is True
    assert home["team_id"] == 1610612752
    assert home["opponent_team_id"] == 1610612750
    assert home["points"] == 17
    assert home["fg3m"] == 3
    assert away["is_home"] is False
    assert away["player_name"] == "Jaden McDaniels"
    assert away["plus_minus"] == -9


def test_coverage_row_reports_complete_only_when_everything_loaded() -> None:
    full = _coverage_row(
        season_start_year=2023,
        season_code=20232024,
        game_type_prefixes=("002", "004"),
        scheduled_games=1312,
        loaded_games=1312,
        loaded_player_rows=40000,
        failed_games=0,
        first_game_date="2023-10-24",
        last_game_date="2024-06-17",
    )
    partial = _coverage_row(
        season_start_year=2024,
        season_code=20242025,
        game_type_prefixes=("002",),
        scheduled_games=1230,
        loaded_games=1200,
        loaded_player_rows=38000,
        failed_games=30,
        first_game_date="2024-10-22",
        last_game_date="2025-04-13",
    )
    assert full.status == "complete"
    assert full.game_type_prefixes == "002,004"
    assert partial.status == "partial"
