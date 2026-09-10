"""Integrity helpers shared by the NFL corpus backup and restore entry points.

An NFL-owned copy of wnba-oracle/scripts/corpus_backup_common.py's validation
discipline (manifest schema, SHA-256 hashing, snapshot verification). Not a
shared import: sport applications must not import one another. This module
uses oracle_core.storage.normalize_postgres_url (provider-neutral) instead of
any WNBA-specific wrapper, and stdlib csv instead of pandas, since nfl-oracle
does not carry that dependency and does not need it for three small tables.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import os
import pathlib
import tempfile
import urllib.parse
from collections.abc import Mapping, Sequence
from typing import Any

SNAPSHOT_SCHEMA_VERSION = 1

# Only the irreplaceable, decision-time records: what we picked (frozen
# lineups), what we knew when we picked it (prepared decisions: the input
# context bundle and the output recommendation), and how it actually scored
# (dayclose grades). model_bundle / active_model artifacts are reproducible
# from Corpus G and are intentionally not backed up here.
TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "frozen_lineups": (
        "slate_date",
        "contest_id",
        "sequence",
        "digest",
        "previous_digest",
        "frozen_at",
        "decision_at",
        "model_fingerprint",
        "input_fingerprint",
        "lineup_json",
        "slate_json",
    ),
    "prepared_decisions": ("day", "sha256", "created_at", "payload_json"),
    "dayclose_grades": ("day", "sha256", "created_at", "payload_json"),
}


class SnapshotValidationError(ValueError):
    """A backup manifest or payload failed local integrity validation."""


def portable_postgres_url(url: str) -> str:
    """Remove a machine-local TLS root path; PGSSLROOTCERT (libpq) takes over."""

    from oracle_core.storage import normalize_postgres_url

    parsed = urllib.parse.urlsplit(url)
    query = [
        (name, value)
        for name, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if name.lower() != "sslrootcert"
    ]
    rebuilt = urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
    )
    return normalize_postgres_url(rebuilt)


def require_verified_tls(url: str) -> None:
    """Reject a database connection that does not authenticate the server."""

    parsed = urllib.parse.urlsplit(url)
    query = {
        name.lower(): value.lower()
        for name, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    }
    if query.get("sslmode") not in {"verify-ca", "verify-full"}:
        raise RuntimeError("database URL must use sslmode=verify-ca or verify-full")


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: pathlib.Path, payload: bytes) -> None:
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


def rows_to_csv_bytes(rows: Sequence[Mapping[str, Any]], columns: tuple[str, ...]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), extrasaction="raise")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue().encode("utf-8")


def table_entry(path: pathlib.Path, *, rows: int) -> dict[str, Any]:
    return {
        "file": path.name,
        "columns": list(TABLE_COLUMNS[path.stem]),
        "rows": rows,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def build_manifest(
    snapshot_dir: pathlib.Path,
    row_counts: Mapping[str, int],
    *,
    generated_at: dt.datetime | None = None,
) -> dict[str, Any]:
    timestamp = generated_at or dt.datetime.now(dt.UTC)
    tables: dict[str, dict[str, Any]] = {}
    for table in sorted(row_counts):
        tables[table] = table_entry(snapshot_dir / f"{table}.csv", rows=row_counts[table])
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at_utc": timestamp.astimezone(dt.UTC).replace(microsecond=0).isoformat(),
        "transaction": {"read_only": True},
        "tables": tables,
    }


def assert_no_regression(
    manifest: Mapping[str, Any],
    previous_manifest_path: pathlib.Path | None,
    *,
    allow_regression: bool,
) -> None:
    """Reject a smaller corpus than the previous backup unless explicitly allowed."""

    if previous_manifest_path is None or not previous_manifest_path.is_file():
        return
    try:
        previous = json.loads(previous_manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("previous corpus manifest could not be read") from exc
    previous_tables = previous.get("tables") if isinstance(previous, dict) else None
    current_tables = manifest.get("tables")
    if not isinstance(previous_tables, dict) or not isinstance(current_tables, dict):
        raise RuntimeError("previous corpus manifest has an invalid shape")

    regressions: list[str] = []
    for table in sorted(TABLE_COLUMNS):
        previous_entry = previous_tables.get(table)
        current_entry = current_tables.get(table)
        if not isinstance(previous_entry, dict) or not isinstance(current_entry, dict):
            continue
        previous_rows = previous_entry.get("rows")
        current_rows = current_entry.get("rows")
        if (
            isinstance(previous_rows, int)
            and isinstance(current_rows, int)
            and current_rows < previous_rows
        ):
            regressions.append(f"{table} row count decreased ({previous_rows} -> {current_rows})")
    if regressions and not allow_regression:
        raise RuntimeError("corpus backup regression: " + "; ".join(regressions))


def validate_snapshot(snapshot_dir: pathlib.Path) -> dict[str, Any]:
    """Validate manifest shape, the exact table set, byte counts, and hashes."""

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
    if not isinstance(tables, dict) or set(tables) != set(TABLE_COLUMNS):
        raise SnapshotValidationError("backup manifest does not list the expected corpus tables")
    for table, expected_columns in TABLE_COLUMNS.items():
        entry = tables.get(table)
        if not isinstance(entry, dict):
            raise SnapshotValidationError(f"backup manifest entry for {table} is invalid")
        filename = entry.get("file")
        if filename != f"{table}.csv":
            raise SnapshotValidationError(f"backup manifest file name for {table} is invalid")
        payload = snapshot_dir / filename
        if not payload.is_file():
            raise SnapshotValidationError(f"backup payload for {table} is missing")
        if entry.get("columns") != list(expected_columns):
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
        if not isinstance(expected_rows, int) or expected_rows < 0:
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
