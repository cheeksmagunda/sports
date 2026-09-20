from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from oracle_core.artifacts import (
    atomic_write_bytes,
    atomic_write_json,
    prune_content_addressed_directory,
    sha256_bytes,
    sha256_file,
    verify_sha256,
    write_artifact,
)


def test_atomic_write_replaces_file_and_applies_mode(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "artifact.bin"
    destination.parent.mkdir()
    destination.write_bytes(b"old")

    result = atomic_write_bytes(destination, b"new", mode=0o600)

    assert result == destination
    assert destination.read_bytes() == b"new"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(destination.parent.glob(".artifact.bin.*.tmp"))


def test_atomic_json_is_canonical_and_readable(tmp_path: Path) -> None:
    destination = tmp_path / "value.json"

    atomic_write_json(destination, {"z": 1, "a": ["value"]})

    assert destination.read_text() == '{"a":["value"],"z":1}\n'
    assert json.loads(destination.read_text()) == {"a": ["value"], "z": 1}


def test_write_artifact_verifies_before_replacing(tmp_path: Path) -> None:
    destination = tmp_path / "model.bin"
    destination.write_bytes(b"previous")

    with pytest.raises(ValueError, match="SHA-256"):
        write_artifact(destination, b"replacement", expected_sha256="0" * 64)

    assert destination.read_bytes() == b"previous"

    expected = sha256_bytes(b"replacement")
    info = write_artifact(destination, b"replacement", expected_sha256=expected)
    assert info.sha256 == expected
    assert info.size == 11
    assert sha256_file(destination) == expected
    assert verify_sha256(destination, expected.upper())
    assert not verify_sha256(destination, "not-a-digest")


def test_prune_content_addressed_directory_removes_old_files_only(tmp_path: Path) -> None:
    root = tmp_path / "observations"
    old_shard = root / "ab"
    old_shard.mkdir(parents=True)
    old_file = old_shard / "old.json"
    old_file.write_bytes(b"stale")
    new_shard = root / "cd"
    new_shard.mkdir(parents=True)
    new_file = new_shard / "fresh.json"
    new_file.write_bytes(b"kept")

    now = 1_000_000.0
    import os

    os.utime(old_file, (now - 100_000, now - 100_000))
    os.utime(new_file, (now - 10, now - 10))

    result = prune_content_addressed_directory(root, max_age_seconds=3_600, now=now)

    assert result.removed_count == 1
    assert result.removed_bytes == len(b"stale")
    assert result.scanned_count == 2
    assert not old_file.exists()
    assert not old_shard.exists()  # emptied shard directory is also removed
    assert new_file.exists()


def test_prune_content_addressed_directory_dry_run_reports_without_deleting(tmp_path: Path) -> None:
    root = tmp_path / "observations"
    root.mkdir()
    stale = root / "stale.json"
    stale.write_bytes(b"x" * 10)

    import os

    now = 1_000_000.0
    os.utime(stale, (now - 100_000, now - 100_000))

    result = prune_content_addressed_directory(root, max_age_seconds=3_600, now=now, dry_run=True)

    assert result.removed_count == 1
    assert result.removed_bytes == 10
    assert stale.exists()


def test_prune_content_addressed_directory_missing_root_is_a_noop(tmp_path: Path) -> None:
    result = prune_content_addressed_directory(tmp_path / "does-not-exist", max_age_seconds=1)
    assert result.removed_count == 0
    assert result.scanned_count == 0
