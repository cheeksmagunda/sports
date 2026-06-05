"""wnba_game_logs: per-game box scores from stats.wnba.com (nba_api).

One row per (game_date, player_id). Columns mirror the parquet written by
scripts/backfill_minutes.py: identity (player_name, first_initial, last_name,
team, season) plus 13 box-score stats and minutes. Source of truth for the
minutes/role model (D54) and validate_minutes_model analysis.

Revision ID: 20260605_0004
Revises: 20260527_0003
Create Date: 2026-06-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260605_0004"
down_revision: str | None = "20260527_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wnba_game_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("game_date", sa.String(10), nullable=False),
        sa.Column("player_id", sa.BigInteger, nullable=False),
        sa.Column("player_name", sa.String(128), nullable=False),
        sa.Column("first_initial", sa.String(4), nullable=False),
        sa.Column("last_name", sa.String(64), nullable=False),
        sa.Column("team", sa.String(8), nullable=False),
        sa.Column("min", sa.Float, nullable=False),
        sa.Column("season", sa.String(8), nullable=False),
        sa.Column("pts", sa.Float, nullable=False),
        sa.Column("reb", sa.Float, nullable=False),
        sa.Column("oreb", sa.Float, nullable=False),
        sa.Column("dreb", sa.Float, nullable=False),
        sa.Column("ast", sa.Float, nullable=False),
        sa.Column("stl", sa.Float, nullable=False),
        sa.Column("blk", sa.Float, nullable=False),
        sa.Column("tov", sa.Float, nullable=False),
        sa.Column("fgm", sa.Float, nullable=False),
        sa.Column("fga", sa.Float, nullable=False),
        sa.Column("fg3m", sa.Float, nullable=False),
        sa.Column("ftm", sa.Float, nullable=False),
        sa.Column("fta", sa.Float, nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "game_date", "player_id", name="uq_wnba_game_logs_date_player"
        ),
    )
    op.create_index("ix_wnba_game_logs_game_date", "wnba_game_logs", ["game_date"])
    op.create_index("ix_wnba_game_logs_player_id", "wnba_game_logs", ["player_id"])
    op.create_index("ix_wnba_game_logs_season", "wnba_game_logs", ["season"])


def downgrade() -> None:
    op.drop_index("ix_wnba_game_logs_season", "wnba_game_logs")
    op.drop_index("ix_wnba_game_logs_player_id", "wnba_game_logs")
    op.drop_index("ix_wnba_game_logs_game_date", "wnba_game_logs")
    op.drop_table("wnba_game_logs")
