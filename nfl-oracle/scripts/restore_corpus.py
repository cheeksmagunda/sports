#!/usr/bin/env python3
"""Validate and explicitly restore a verified NFL corpus backup snapshot.

The default mode only validates the manifest and SHA-256 hashes. Applying a
restore requires both ``--apply`` and ``--confirm-restore RESTORE_CORPUS``,
then reads ``NFL_DATABASE_RESTORE_URL`` from the environment (falling back to
``NFL_DATABASE_URL`` for local runs). It never prints the database URL or a row
payload.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import sys
from typing import Any

from nfl_corpus_backup_common import SnapshotValidationError, validate_snapshot
from sqlalchemy import create_engine

from nfl_oracle.recommendations.dayclose import DAYCLOSE_GRADE_KIND_PREFIX
from nfl_oracle.recommendations.schema import Slate, fingerprint
from nfl_oracle.recommendations.store import RecommendationStore, migrate

PREPARED_KIND_PREFIX = "prepared"


def _csv_records(path: pathlib.Path) -> list[dict[str, str]]:
    csv.field_size_limit(sys.maxsize)
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise SnapshotValidationError(f"backup payload for {path.name} could not be read") from exc


def _required(row: dict[str, str], column: str) -> str:
    value = row.get(column)
    if value is None or value == "":
        raise SnapshotValidationError(f"backup payload column {column} is missing")
    return value


def _json_field(row: dict[str, str], column: str) -> Any:
    try:
        return json.loads(_required(row, column))
    except json.JSONDecodeError as exc:
        raise SnapshotValidationError(f"backup payload column {column} is not valid JSON") from exc


def _freeze_record(row: dict[str, str]) -> dict[str, Any]:
    slate_json = _json_field(row, "slate_json")
    lineup_json = _json_field(row, "lineup_json")
    try:
        contest_id = int(_required(row, "contest_id"))
        sequence = int(_required(row, "sequence"))
        slate = Slate.model_validate(slate_json)
    except (TypeError, ValueError) as exc:
        raise SnapshotValidationError("backup freeze metadata is invalid") from exc
    if slate.contest.contest_id != contest_id:
        raise SnapshotValidationError("backup freeze contest_id does not match slate payload")
    request = {
        "slate": slate_json,
        "lineup": lineup_json,
        "model_fingerprint": _required(row, "model_fingerprint"),
        "input_fingerprint": _required(row, "input_fingerprint"),
        "decision_at": _required(row, "decision_at"),
    }
    record = {
        **request,
        "schema_version": 1,
        "slate_date": _required(row, "slate_date"),
        "contest_id": contest_id,
        "sequence": sequence,
        "previous_digest": row.get("previous_digest") or None,
        "request_hash": fingerprint(request),
        "frozen_at": _required(row, "frozen_at"),
        "cutoff_at": slate.cutoff().isoformat(),
        "contest_entry": False,
        "digest": _required(row, "digest"),
    }
    try:
        RecommendationStore._verify(record)
    except ValueError as exc:
        raise SnapshotValidationError("backup freeze digest does not match its payload") from exc
    return record


def _artifact_record(
    row: dict[str, str],
    *,
    kind_prefix: str,
) -> dict[str, Any]:
    payload = _json_field(row, "payload_json")
    sha256 = _required(row, "sha256")
    if fingerprint(payload) != sha256:
        raise SnapshotValidationError("backup artifact hash does not match its payload")
    return {
        "sha256": sha256,
        "kind": f"{kind_prefix}:{_required(row, 'day')}",
        "payload": payload,
        "created_at": _required(row, "created_at"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-restore")
    parser.add_argument("--migrate", action="store_true")
    args = parser.parse_args()

    snapshot_dir = pathlib.Path(args.snapshot_dir)
    try:
        manifest = validate_snapshot(snapshot_dir)
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

    database_url = (
        os.environ.get("NFL_DATABASE_RESTORE_URL", "").strip()
        or os.environ.get("NFL_DATABASE_URL", "").strip()
    )
    if not database_url:
        parser.error("NFL_DATABASE_RESTORE_URL or NFL_DATABASE_URL is required for --apply")

    try:
        restored = apply_snapshot(snapshot_dir, database_url, migrate_first=args.migrate)
    except Exception as exc:
        print(f"ERROR: corpus restore failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    print(
        "restored corpus rows:", ", ".join(f"{name}={restored[name]}" for name in sorted(restored))
    )
    return 0


def _build_backup(snapshot_dir: pathlib.Path) -> dict[str, Any]:
    freezes = [_freeze_record(row) for row in _csv_records(snapshot_dir / "frozen_lineups.csv")]
    artifacts = [
        *[
            _artifact_record(row, kind_prefix=PREPARED_KIND_PREFIX)
            for row in _csv_records(snapshot_dir / "prepared_decisions.csv")
        ],
        *[
            _artifact_record(row, kind_prefix=DAYCLOSE_GRADE_KIND_PREFIX)
            for row in _csv_records(snapshot_dir / "dayclose_grades.csv")
        ],
    ]
    body = {"schema_version": 1, "freezes": freezes, "runs": [], "artifacts": artifacts}
    return {**body, "digest": fingerprint(body)}


def apply_snapshot(
    snapshot_dir: pathlib.Path,
    database_url: str,
    *,
    migrate_first: bool = False,
) -> dict[str, int]:
    """Restore validated CSVs into an empty writable decisions store."""

    from oracle_core.storage import normalize_postgres_url

    backup = _build_backup(snapshot_dir)
    engine = (
        create_engine(database_url)
        if database_url.startswith("sqlite:")
        else create_engine(normalize_postgres_url(database_url))
    )
    try:
        if migrate_first:
            migrate(engine)
        store = RecommendationStore(engine, writable=True)
        store.restore_backup(backup)
    finally:
        engine.dispose()
    return {
        "artifacts": len(backup["artifacts"]),
        "freezes": len(backup["freezes"]),
        "runs": len(backup["runs"]),
    }


if __name__ == "__main__":
    sys.exit(main())
