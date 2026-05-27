"""Pandera schema sanity checks. Validate that good frames pass and obvious
violations fail."""

from __future__ import annotations

import polars as pl
import pytest
from pandera.errors import SchemaError

from wnba_oracle.schemas import (
    OddsSchema,
    PlayerPoolSchema,
    RotowireLineupSchema,
)


def test_player_pool_good() -> None:
    df = pl.DataFrame(
        {
            "platform_id": ["598"],
            "first_name": ["A'ja"],
            "last_name": ["Wilson"],
            "display_name": ["A. Wilson"],
            "position": ["C"],
            "team": ["LVA"],
            "multiplier_bonus": [1.5],
            "primary_ranking": [3],
            "injury_status": ["Active"],
        }
    )
    PlayerPoolSchema.validate(df)


def test_player_pool_rejects_out_of_range_boost() -> None:
    df = pl.DataFrame(
        {
            "platform_id": ["1"],
            "first_name": [None],
            "last_name": [None],
            "display_name": [None],
            "position": ["G"],
            "team": ["LVA"],
            "multiplier_bonus": [5.0],
            "primary_ranking": [None],
            "injury_status": [None],
        }
    )
    with pytest.raises(SchemaError):
        PlayerPoolSchema.validate(df)


def test_rotowire_starter_slot_bounded() -> None:
    df = pl.DataFrame(
        {
            "team": ["LVA"],
            "opponent": ["NYL"],
            "is_home": [True],
            "starter_slot": [6],
            "player_name": ["X"],
            "position": ["G"],
            "injury_status": [""],
            "confirmed": [True],
        }
    )
    with pytest.raises(SchemaError):
        RotowireLineupSchema.validate(df)


def test_odds_good() -> None:
    df = pl.DataFrame(
        {
            "home_team": ["Las Vegas Aces"],
            "away_team": ["New York Liberty"],
            "commence_time": ["2026-05-27T23:00:00Z"],
            "h2h_home": [1.85],
            "h2h_away": [1.95],
            "spread_home_point": [-1.5],
            "spread_home_price": [1.91],
            "spread_away_point": [1.5],
            "spread_away_price": [1.91],
            "total_point": [161.5],
            "total_over_price": [1.91],
            "total_under_price": [1.91],
        }
    )
    OddsSchema.validate(df)
