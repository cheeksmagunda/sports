from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from oracle_core.artifacts import (
    atomic_write_bytes,
    atomic_write_json,
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
