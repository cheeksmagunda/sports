"""frozen_lineups: append-only freezes + slate_meta lock times.

Incident 2026-06-08: the D75 late re-freeze (FROZEN_UPSERT, ON CONFLICT
(slate_date, model_sha) DO UPDATE) overwrote the 21:00 UTC frozen row in
place. The operator had already entered the 21:00 lineup and there was no
audit copy to reconstruct what shipped at lock time.

This migration makes frozen_lineups append-only (D82):
  freeze_seq  per-(slate_date, model_sha) monotonically increasing sequence
  frozen_via  write-path provenance, promoted from metadata_json
The old (slate_date, model_sha) unique constraint is replaced by
(slate_date, model_sha, freeze_seq) so every freeze fire appends a new row.
Serving reads the max freeze_seq; audits read all rows.

It also creates slate_meta (D83): per-slate first tip and contest lock
times, captured by job1, so the late re-freeze can be gated on lock time.

Existing rows backfill freeze_seq by frozen_at order within each
(slate_date, model_sha) group and frozen_via from metadata_json->>'frozen_via'
(falling back to 'unknown' for pre-D75 rows that never carried it).

Revision ID: 20260610_0006
Revises: 20260605_0005
Create Date: 2026-06-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260610_0006"
down_revision: str | None = "20260605_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "frozen_lineups", sa.Column("freeze_seq", sa.Integer, nullable=True)
    )
    op.add_column(
        "frozen_lineups", sa.Column("frozen_via", sa.String(32), nullable=True)
    )
    op.execute(
        """
        UPDATE frozen_lineups f SET
            freeze_seq = sub.rn,
            frozen_via = COALESCE(f.metadata_json->>'frozen_via', 'unknown')
        FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY slate_date, model_sha ORDER BY frozen_at ASC, id ASC
            ) AS rn
            FROM frozen_lineups
        ) sub
        WHERE f.id = sub.id
        """
    )
    op.alter_column("frozen_lineups", "freeze_seq", nullable=False)
    op.alter_column("frozen_lineups", "frozen_via", nullable=False)
    op.drop_constraint(
        "uq_frozen_lineups_slate_model", "frozen_lineups", type_="unique"
    )
    op.create_unique_constraint(
        "uq_frozen_lineups_slate_model_seq",
        "frozen_lineups",
        ["slate_date", "model_sha", "freeze_seq"],
    )

    # slate_meta: per-slate timing facts (earliest tip, contest lock when the
    # platform exposes one). Written by job1, read by the job2 late-refreeze
    # gate. A row with NULL timestamps is valid: it records that job1 looked
    # and found nothing, and the gate falls back to a hard deadline.
    op.create_table(
        "slate_meta",
        sa.Column("slate_date", sa.Date, primary_key=True),
        sa.Column("first_tip_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contest_lock_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("payload_json", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("slate_meta")
    # Collapse back to one row per (slate_date, model_sha): keep the highest
    # freeze_seq (what serving showed last). This is lossy by design; the
    # whole point of the upgrade is that the old schema cannot hold history.
    op.execute(
        """
        DELETE FROM frozen_lineups f USING frozen_lineups newer
        WHERE f.slate_date = newer.slate_date
          AND f.model_sha = newer.model_sha
          AND f.freeze_seq < newer.freeze_seq
        """
    )
    op.drop_constraint(
        "uq_frozen_lineups_slate_model_seq", "frozen_lineups", type_="unique"
    )
    op.create_unique_constraint(
        "uq_frozen_lineups_slate_model",
        "frozen_lineups",
        ["slate_date", "model_sha"],
    )
    op.drop_column("frozen_lineups", "frozen_via")
    op.drop_column("frozen_lineups", "freeze_seq")
