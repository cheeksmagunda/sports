"""Pure integrity tests for the off-platform corpus backup and restore tools."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import pathlib
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts"
TABLES = {"slate_labels", "contest_leaderboards"}


def _load_common() -> ModuleType:
    spec = importlib.util.spec_from_file_location("corpus_backup_common", SCRIPTS_DIR / "corpus_backup_common.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_valid_snapshot(common: ModuleType, root: pathlib.Path) -> None:
    details: dict[str, dict[str, object]] = {}
    for table in sorted(TABLES):
        columns = list(common.CORPUS_COLUMNS[table])
        payload = ",".join(columns) + "\n" + ",".join("1" for _ in columns) + "\n"
        common.atomic_write_bytes(root / f"{table}.csv", payload.encode())
        details[table] = {
            "file": f"{table}.csv",
            "columns": columns,
            "rows": 1,
            "slates": 1,
            "max_slate": "2026-08-20",
        }
    manifest = common.build_manifest(
        root,
        details,
        generated_at=dt.datetime(2026, 8, 20, 12, tzinfo=dt.UTC),
    )
    common.atomic_write_json(root / "manifest.json", manifest)


def test_manifest_binds_hashes_and_repeatable_read_metadata(tmp_path) -> None:
    common = _load_common()
    _write_valid_snapshot(common, tmp_path)

    manifest = common.validate_snapshot(tmp_path, expected_tables=TABLES)

    assert manifest["transaction"] == {"isolation": "REPEATABLE READ", "read_only": True}
    assert manifest["tables"]["slate_labels"]["sha256"]
    assert manifest["tables"]["contest_leaderboards"]["bytes"] > 0


def test_restore_validation_rejects_tampered_payload(tmp_path) -> None:
    common = _load_common()
    _write_valid_snapshot(common, tmp_path)
    payload = (tmp_path / "slate_labels.csv").read_text(encoding="utf-8")
    (tmp_path / "slate_labels.csv").write_text(
        payload.replace("1", "2", 1), encoding="utf-8"
    )

    with pytest.raises(common.SnapshotValidationError, match="hash"):
        common.validate_snapshot(tmp_path, expected_tables=TABLES)


def test_validation_rejects_a_hash_valid_but_truncated_payload(tmp_path) -> None:
    common = _load_common()
    details: dict[str, dict[str, object]] = {}
    for table in sorted(TABLES):
        columns = list(common.CORPUS_COLUMNS[table])
        common.atomic_write_bytes(
            tmp_path / f"{table}.csv",
            (",".join(columns) + "\n").encode(),
        )
        details[table] = {
            "file": f"{table}.csv",
            "columns": columns,
            "rows": 1,
            "slates": 1,
        }
    manifest = common.build_manifest(tmp_path, details)
    common.atomic_write_json(tmp_path / "manifest.json", manifest)

    with pytest.raises(common.SnapshotValidationError, match="row count"):
        common.validate_snapshot(tmp_path, expected_tables=TABLES)


def test_backup_rejects_regression_against_previous_manifest(tmp_path) -> None:
    common = _load_common()
    _write_valid_snapshot(common, tmp_path)
    backup = _load_script("backup_corpus")
    current = common.validate_snapshot(tmp_path, expected_tables=TABLES)
    previous = json.loads(json.dumps(current))
    previous["tables"]["slate_labels"]["rows"] = 2
    previous_path = tmp_path / "previous.json"
    previous_path.write_text(json.dumps(previous), encoding="utf-8")

    with pytest.raises(RuntimeError, match="row count decreased"):
        backup._assert_no_regression(current, previous_path, allow_regression=False)

    backup._assert_no_regression(current, previous_path, allow_regression=True)


def test_backup_url_removes_only_the_machine_local_tls_root_path() -> None:
    _load_common()
    backup = _load_script("backup_corpus")

    portable = backup._portable_database_url(
        "postgresql://user:password@example.invalid:5432/database"
        "?sslmode=verify-ca&sslrootcert=%2Fold%2Fmachine%2Froot.crt&application_name=backup"
    )

    assert "sslrootcert" not in portable
    assert "sslmode=verify-ca" in portable
    assert "application_name=backup" in portable


def test_restore_entry_point_only_accepts_a_verified_snapshot(tmp_path) -> None:
    common = _load_common()
    _write_valid_snapshot(common, tmp_path)
    restore = _load_script("restore_corpus")

    manifest = restore.verify_snapshot(tmp_path)
    assert set(manifest["tables"]) == TABLES

    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(common.SnapshotValidationError):
        restore.verify_snapshot(tmp_path)


def test_restore_records_convert_missing_numeric_values_to_null() -> None:
    common = _load_common()
    del common
    restore = _load_script("restore_corpus")

    import pandas as pd

    records = restore._nullable_records(
        pd.DataFrame({"drafts": [12.0, float("nan")]}), integer_columns={"drafts"}
    )

    assert records == [{"drafts": 12}, {"drafts": None}]


def test_restore_apply_uses_one_transaction_and_disposes_engine(
    monkeypatch, tmp_path
) -> None:
    common = _load_common()
    _write_valid_snapshot(common, tmp_path)
    restore = _load_script("restore_corpus")
    engine = MagicMock()
    connection = MagicMock()
    engine.begin.return_value.__enter__.return_value = connection

    import sqlalchemy

    def create_engine(*args, **kwargs):
        del args, kwargs
        return engine

    monkeypatch.setattr(sqlalchemy, "create_engine", create_engine)

    restored = restore.apply_snapshot(tmp_path, "postgresql://example.invalid/database")

    assert restored == {"contest_leaderboards": 1, "slate_labels": 1}
    assert connection.execute.call_count == 2
    engine.begin.assert_called_once_with()
    engine.dispose.assert_called_once_with()


def test_export_uses_one_read_only_snapshot_and_publishes_verified_manifest(
    monkeypatch, tmp_path
) -> None:
    common = _load_common()
    backup = _load_script("backup_corpus")
    connection = MagicMock()
    connection.execution_options.return_value = connection
    connection.begin.return_value.__enter__.return_value = connection
    engine = MagicMock()
    engine.connect.return_value = connection

    import pandas as pd

    frames = iter(
        [
            pd.DataFrame(
                {
                    column: ["2026-08-20" if column == "slate_date" else 1]
                    for column in common.CORPUS_COLUMNS["slate_labels"]
                }
            ),
            pd.DataFrame(
                {
                    column: ["2026-08-20" if column == "slate_date" else 1]
                    for column in common.CORPUS_COLUMNS["contest_leaderboards"]
                }
            ),
        ]
    )

    def read_sql(statement, observed_connection):
        assert statement is not None
        assert observed_connection is connection
        return next(frames)

    monkeypatch.setattr(backup.pd, "read_sql", read_sql)

    manifest = backup.export_corpus(engine, tmp_path)

    assert manifest["transaction"] == {"isolation": "REPEATABLE READ", "read_only": True}
    assert set(manifest["tables"]) == TABLES
    assert (tmp_path / "manifest.json").is_file()
    connection.execution_options.assert_called_once_with(isolation_level="REPEATABLE READ")
    assert "SET TRANSACTION READ ONLY" in str(connection.execute.call_args.args[0])
    connection.close.assert_called_once_with()
