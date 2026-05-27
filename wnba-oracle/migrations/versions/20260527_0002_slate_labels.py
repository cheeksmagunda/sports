"""slate_labels: per-slate per-player training labels (real_score + card_boost).

Revision ID: 20260527_0002
Revises: 20260526_0001
Create Date: 2026-05-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0002"
down_revision: str | None = "20260526_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "slate_labels",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("contest_id", sa.Integer, nullable=False),
        sa.Column("slate_date", sa.String(16), nullable=False),
        sa.Column("section", sa.String(48), nullable=False),
        sa.Column("platform_player_id", sa.BigInteger, nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("team_key", sa.String(8), nullable=False),
        sa.Column("card_boost", sa.Float, nullable=False),
        sa.Column("drafts", sa.Integer, nullable=True),
        sa.Column("real_score", sa.Float, nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "contest_id", "platform_player_id", name="uq_slate_labels_contest_player"
        ),
    )
    op.create_index("ix_slate_labels_slate_date", "slate_labels", ["slate_date"])
    op.create_index(
        "ix_slate_labels_platform_player_id", "slate_labels", ["platform_player_id"]
    )


def downgrade() -> None:
    op.drop_table("slate_labels")
