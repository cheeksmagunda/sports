"""Integrity helpers shared by the corpus backup and restore entry points."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import pathlib
import tempfile
from collections.abc import Mapping
from typing import Any

SNAPSHOT_SCHEMA_VERSION = 1
CORPUS_COLUMNS = {
    "slate_labels": (
        "contest_id",
        "slate_date",
        "section",
        "platform_player_id",
        "display_name",
        "team_key",
        "card_boost",
        "drafts",
        "real_score",
        "ingested_at",
    ),
    "contest_leaderboards": (
        "contest_id",
        "slate_date",
        "entry_id",
        "rank",
        "paged_rank",
        "user_id",
        "score",
        "lineup",
        "num_brawlers",
        "ingested_at",
    ),
}


class SnapshotValidationError(ValueError):
    """A backup manifest or payload failed local integrity validation."""


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: pathlib.Path, payload: bytes) -> None:
    """Write a complete file before replacing the published path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = pathlib.Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def atomic_write_json(path: pathlib.Path, value: Mapping[str, Any]) -> None:
    body = json.dumps(value, indent=2, sort_keys=True, default=str).encode() + b"\n"
    atomic_write_bytes(path, body)


def table_entry(path: pathlib.Path, details: Mapping[str, Any]) -> dict[str, Any]:
    """Add the checksum and byte count for a completed table payload."""

    return {
        **dict(details),
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def build_manifest(
    snapshot_dir: pathlib.Path,
    table_details: Mapping[str, Mapping[str, Any]],
    *,
    generated_at: dt.datetime | None = None,
) -> dict[str, Any]:
    """Build a versioned manifest after every table file has been published."""

    timestamp = generated_at or dt.datetime.now(dt.UTC)
    tables: dict[str, dict[str, Any]] = {}
    for table, details in sorted(table_details.items()):
        filename = details.get("file")
        if not isinstance(filename, str) or not filename:
            raise ValueError(f"backup details for {table} must include a file name")
        tables[table] = table_entry(snapshot_dir / filename, details)
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at_utc": timestamp.astimezone(dt.UTC).replace(microsecond=0).isoformat(),
        "transaction": {"isolation": "REPEATABLE READ", "read_only": True},
        "tables": tables,
    }


def validate_snapshot(
    snapshot_dir: pathlib.Path, *, expected_tables: set[str]
) -> dict[str, Any]:
    """Validate manifest shape, exact table set, byte counts, and SHA-256 hashes."""

    manifest_path = snapshot_dir / "manifest.json"
    try:
        decoded = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotValidationError("backup manifest could not be read") from exc
    if not isinstance(decoded, dict):
        raise SnapshotValidationError("backup manifest must be an object")
    if decoded.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise SnapshotValidationError("backup manifest has an unsupported schema version")
    tables = decoded.get("tables")
    if not isinstance(tables, dict) or set(tables) != expected_tables:
        raise SnapshotValidationError("backup manifest does not list the expected corpus tables")
    for table in sorted(expected_tables):
        entry = tables.get(table)
        if not isinstance(entry, dict):
            raise SnapshotValidationError(f"backup manifest entry for {table} is invalid")
        filename = entry.get("file")
        if filename != f"{table}.csv":
            raise SnapshotValidationError(f"backup manifest file name for {table} is invalid")
        payload = snapshot_dir / filename
        if not payload.is_file():
            raise SnapshotValidationError(f"backup payload for {table} is missing")
        expected_columns = CORPUS_COLUMNS.get(table)
        if expected_columns is None:
            raise SnapshotValidationError(f"backup schema for {table} is not declared")
        manifest_columns = entry.get("columns")
        if manifest_columns != list(expected_columns):
            raise SnapshotValidationError(f"backup manifest columns for {table} are invalid")
        try:
            with payload.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
                actual_rows = sum(1 for _ in reader)
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            raise SnapshotValidationError(f"backup payload for {table} is not valid CSV") from exc
        if header != list(expected_columns):
            raise SnapshotValidationError(f"backup payload columns for {table} are invalid")
        expected_rows = entry.get("rows")
        if not isinstance(expected_rows, int) or expected_rows <= 0:
            raise SnapshotValidationError(f"backup manifest row count for {table} is invalid")
        if actual_rows != expected_rows:
            raise SnapshotValidationError(f"backup payload row count for {table} does not match")
        expected_size = entry.get("bytes")
        if not isinstance(expected_size, int) or expected_size != payload.stat().st_size:
            raise SnapshotValidationError(f"backup payload byte count for {table} does not match")
        expected_hash = entry.get("sha256")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise SnapshotValidationError(f"backup payload hash for {table} is invalid")
        if sha256_file(payload) != expected_hash:
            raise SnapshotValidationError(f"backup payload hash for {table} does not match")
    return decoded
