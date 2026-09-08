"""Add durable external account access windows.

Revision ID: 20260826_0011
Revises: 20260820_0010
Create Date: 2026-08-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_0011"
down_revision: str | None = "20260820_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_access_windows",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(128), nullable=False),
        sa.Column("consumer", sa.String(64), nullable=False),
        sa.Column("slate_date", sa.Date(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=True),
    )
    op.create_index(
        "ix_external_access_scope_started",
        "external_access_windows",
        ["scope", "started_at"],
    )
    op.create_index(
        "ix_external_access_consumer_slate",
        "external_access_windows",
        ["consumer", "slate_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_external_access_consumer_slate", table_name="external_access_windows")
    op.drop_index("ix_external_access_scope_started", table_name="external_access_windows")
    op.drop_table("external_access_windows")
