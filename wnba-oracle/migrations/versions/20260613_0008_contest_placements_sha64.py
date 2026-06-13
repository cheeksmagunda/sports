"""Fix freeze_model_sha column: varchar(40) -> varchar(64).

SHA256 hashes are 64 hex chars; the original migration used 40 (SHA1 length).
The table is new (D90, 2026-06-13) and empty in prod so the ALTER is instant.

Revision ID: 20260613_0008
Revises: 20260613_0007
Create Date: 2026-06-13
"""
from __future__ import annotations

from alembic import op

revision = "20260613_0008"
down_revision = "20260613_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE contest_placements "
        "ALTER COLUMN freeze_model_sha TYPE character varying(64)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE contest_placements "
        "ALTER COLUMN freeze_model_sha TYPE character varying(40)"
    )
