#!/usr/bin/env python3
"""Validate and explicitly restore a verified corpus backup.

The default mode only validates the manifest and SHA-256 hashes. Applying a
restore requires both ``--apply`` and ``--confirm-restore RESTORE_CORPUS``,
then reads ``DATABASE_RESTORE_URL`` from the environment. It never prints the
database URL or a row payload.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
from typing import Any

from corpus_backup_common import SnapshotValidationError, validate_snapshot

from wnba_oracle.common.db_utils import normalize_postgres_url

CORPUS_TABLES = {"slate_labels", "contest_leaderboards"}
INTEGER_COLUMNS = {
    "slate_labels": {"contest_id", "platform_player_id", "drafts"},
    "contest_leaderboards": {
        "contest_id",
        "entry_id",
        "rank",
        "paged_rank",
        "num_brawlers",
    },
}

RESTORE_SQL = {
    "slate_labels": """
        INSERT INTO slate_labels (
            contest_id, slate_date, section, platform_player_id, display_name,
            team_key, card_boost, drafts, real_score, ingested_at
        ) VALUES (
            :contest_id, :slate_date, :section, :platform_player_id, :display_name,
            :team_key, :card_boost, :drafts, :real_score, :ingested_at
        ) ON CONFLICT (contest_id, platform_player_id) DO UPDATE SET
            slate_date = EXCLUDED.slate_date,
            section = EXCLUDED.section,
            display_name = EXCLUDED.display_name,
            team_key = EXCLUDED.team_key,
            card_boost = EXCLUDED.card_boost,
            drafts = EXCLUDED.drafts,
            real_score = EXCLUDED.real_score,
            ingested_at = EXCLUDED.ingested_at
    """,
    "contest_leaderboards": """
        INSERT INTO contest_leaderboards (
            contest_id, slate_date, entry_id, rank, paged_rank, user_id, score,
            lineup, num_brawlers, ingested_at
        ) VALUES (
            :contest_id, :slate_date, :entry_id, :rank, :paged_rank, :user_id, :score,
            CAST(:lineup AS jsonb), :num_brawlers, :ingested_at
        ) ON CONFLICT (contest_id, entry_id) DO UPDATE SET
            slate_date = EXCLUDED.slate_date,
            rank = EXCLUDED.rank,
            paged_rank = EXCLUDED.paged_rank,
            user_id = EXCLUDED.user_id,
            score = EXCLUDED.score,
            lineup = EXCLUDED.lineup,
            num_brawlers = EXCLUDED.num_brawlers,
            ingested_at = EXCLUDED.ingested_at
    """,
}


def verify_snapshot(snapshot_dir: pathlib.Path) -> dict[str, Any]:
    """Return a locally verified manifest or raise a safe validation error."""

    return validate_snapshot(snapshot_dir, expected_tables=CORPUS_TABLES)


def _nullable_records(frame, *, integer_columns: set[str] | None = None) -> list[dict[str, Any]]:
    normalized = frame.astype(object).where(frame.notna(), None)
    records = [dict(record) for record in normalized.to_dict(orient="records")]
    for record in records:
        for column in integer_columns or set():
            if record.get(column) is not None:
                record[column] = int(record[column])
    return records


def apply_snapshot(snapshot_dir: pathlib.Path, database_url: str) -> dict[str, int]:
    """Restore validated CSVs in a single transaction after explicit confirmation."""

    import pandas as pd
    from sqlalchemy import create_engine, text

    restored: dict[str, int] = {}
    engine = create_engine(normalize_postgres_url(database_url))
    try:
        with engine.begin() as connection:
            for table in sorted(CORPUS_TABLES):
                frame = pd.read_csv(snapshot_dir / f"{table}.csv")
                records = _nullable_records(frame, integer_columns=INTEGER_COLUMNS[table])
                if records:
                    connection.execute(text(RESTORE_SQL[table]), records)
                restored[table] = len(records)
    finally:
        engine.dispose()
    return restored


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-restore")
    args = parser.parse_args()

    snapshot_dir = pathlib.Path(args.snapshot_dir)
    try:
        manifest = verify_snapshot(snapshot_dir)
    except SnapshotValidationError as exc:
        print(f"ERROR: backup verification failed: {exc}", file=sys.stderr)
        return 1

    tables = manifest["tables"]
    print(
        "verified corpus backup:",
        ", ".join(f"{name}={tables[name]['rows']}" for name in sorted(tables)),
    )
    if not args.apply:
        print("validation only; pass --apply and --confirm-restore RESTORE_CORPUS to restore")
        return 0
    if args.confirm_restore != "RESTORE_CORPUS":
        parser.error("--apply requires --confirm-restore RESTORE_CORPUS")
    database_url = os.environ.get("DATABASE_RESTORE_URL", "")
    if not database_url:
        parser.error("DATABASE_RESTORE_URL is required for --apply")

    try:
        restored = apply_snapshot(snapshot_dir, database_url)
    except Exception as exc:
        print(f"ERROR: corpus restore failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    print(
        "restored corpus rows:", ", ".join(f"{name}={restored[name]}" for name in sorted(restored))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
