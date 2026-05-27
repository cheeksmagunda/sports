"""Pandera schemas for ingest-layer dataframes.

We use the Polars dialect (`pandera.polars`) because the ingest modules
return Polars dataframes. The schemas are intentionally tight on key
columns (player_id, season, team) and permissive on optional metrics
(plus_minus, advanced rates) because nba_api has occasionally introduced
nulls during in-season schema rolls.
"""

from __future__ import annotations

from pandera.polars import Check, Column, DataFrameSchema

# ---------- Real Sports player pool ------------------------------------

PlayerPoolSchema = DataFrameSchema(
    {
        "platform_id": Column(str, nullable=False),
        "first_name": Column(str, nullable=True),
        "last_name": Column(str, nullable=True),
        "display_name": Column(str, nullable=True),
        "position": Column(str, nullable=True),
        "team": Column(str, Check.str_length(min_value=2, max_value=4), nullable=False),
        "multiplier_bonus": Column(
            float, Check.in_range(0.0, 3.0), nullable=False
        ),
        "primary_ranking": Column(int, nullable=True),
        "injury_status": Column(str, nullable=True),
    },
    strict=False,
    coerce=True,
)

# ---------- Player game log (nba_api playergamelog) --------------------

PlayerGameLogSchema = DataFrameSchema(
    {
        "Player_ID": Column(int, nullable=False),
        "Game_ID": Column(str, nullable=False),
        "GAME_DATE": Column(str, nullable=False),
        "MATCHUP": Column(str, nullable=False),
        "WL": Column(str, nullable=True),
        "MIN": Column(int, Check.in_range(0, 60), nullable=False),
        "PTS": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "REB": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "AST": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "STL": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "BLK": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "TOV": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "FG3M": Column(int, nullable=True),
        "FG3A": Column(int, nullable=True),
        "FTM": Column(int, nullable=True),
        "FTA": Column(int, nullable=True),
        "PLUS_MINUS": Column(int, nullable=True),
    },
    strict=False,
    coerce=True,
)

# ---------- Team pace (advanced team stats) ----------------------------

TeamPaceSchema = DataFrameSchema(
    {
        "TEAM_ID": Column(int, nullable=False),
        "TEAM_NAME": Column(str, nullable=False),
        "GP": Column(int, Check.greater_than(0), nullable=False),
        "PACE": Column(float, Check.in_range(60.0, 110.0), nullable=True),
        "OFF_RATING": Column(float, nullable=True),
        "DEF_RATING": Column(float, nullable=True),
        "NET_RATING": Column(float, nullable=True),
        "TS_PCT": Column(float, Check.in_range(0.0, 1.0), nullable=True),
        "EFG_PCT": Column(float, Check.in_range(0.0, 1.0), nullable=True),
    },
    strict=False,
    coerce=True,
)

# ---------- Player season averages (per-game) --------------------------

PlayerSeasonAveragesSchema = DataFrameSchema(
    {
        "PLAYER_ID": Column(int, nullable=False),
        "PLAYER_NAME": Column(str, nullable=False),
        "TEAM_ID": Column(int, nullable=True),
        "TEAM_ABBREVIATION": Column(str, nullable=True),
        "GP": Column(int, Check.greater_than_or_equal_to(0), nullable=False),
        "MIN": Column(float, Check.in_range(0.0, 40.0), nullable=True),
        "PTS": Column(float, nullable=True),
        "REB": Column(float, nullable=True),
        "AST": Column(float, nullable=True),
    },
    strict=False,
    coerce=True,
)

# ---------- Odds (one row per game) ------------------------------------

OddsSchema = DataFrameSchema(
    {
        "home_team": Column(str, nullable=False),
        "away_team": Column(str, nullable=False),
        "commence_time": Column(str, nullable=False),
        "h2h_home": Column(float, nullable=True),
        "h2h_away": Column(float, nullable=True),
        "spread_home_point": Column(float, nullable=True),
        "spread_home_price": Column(float, nullable=True),
        "spread_away_point": Column(float, nullable=True),
        "spread_away_price": Column(float, nullable=True),
        "total_point": Column(float, Check.in_range(100.0, 220.0), nullable=True),
        "total_over_price": Column(float, nullable=True),
        "total_under_price": Column(float, nullable=True),
    },
    strict=False,
    coerce=True,
)

# ---------- RotoWire lineup entries ------------------------------------

RotowireLineupSchema = DataFrameSchema(
    {
        "team": Column(str, nullable=False),
        "opponent": Column(str, nullable=False),
        "is_home": Column(bool, nullable=False),
        "starter_slot": Column(int, Check.in_range(1, 5), nullable=False),
        "player_name": Column(str, nullable=False),
        "position": Column(str, nullable=True),
        "injury_status": Column(str, nullable=True),
        "confirmed": Column(bool, nullable=False),
    },
    strict=False,
    coerce=True,
)
