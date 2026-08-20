"""Add semantic idempotency keys to append-only freezes.

Revision ID: 20260820_0009
Revises: 20260613_0008
Create Date: 2026-08-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0009"
down_revision: str | None = "20260613_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "frozen_lineups",
        sa.Column("operation_key", sa.String(64), nullable=True),
    )
    # Historical rows remain independently addressable. New writes use stable
    # semantic keys such as ``first`` and ``job2_late_refreeze``.
    op.execute("UPDATE frozen_lineups SET operation_key = 'legacy:' || id::text")
    op.alter_column("frozen_lineups", "operation_key", nullable=False)
    op.create_unique_constraint(
        "uq_frozen_lineups_operation",
        "frozen_lineups",
        ["slate_date", "model_sha", "operation_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_frozen_lineups_operation", "frozen_lineups", type_="unique"
    )
    op.drop_column("frozen_lineups", "operation_key")
