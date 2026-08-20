"""Atomic artifact persistence and integrity verification."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactInfo:
    """Metadata for a fully persisted artifact."""

    path: Path
    sha256: str
    size: int


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 digest for *data*."""

    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | os.PathLike[str], *, chunk_size: int = 1024 * 1024) -> str:
    """Stream a file and return its lowercase SHA-256 digest."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path: str | os.PathLike[str], expected: str) -> bool:
    """Compare a file digest without timing-dependent string comparison."""

    normalized = expected.strip().casefold()
    return len(normalized) == 64 and hmac.compare_digest(sha256_file(path), normalized)


def atomic_write_bytes(
    path: str | os.PathLike[str],
    data: bytes,
    *,
    mode: int = 0o644,
) -> Path:
    """Durably replace *path* with bytes written in the same directory."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, destination)
        _sync_directory(destination.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def atomic_write_json(
    path: str | os.PathLike[str],
    value: Any,
    *,
    mode: int = 0o644,
) -> Path:
    """Serialize canonical JSON and atomically replace *path*."""

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return atomic_write_bytes(path, f"{payload}\n".encode(), mode=mode)


def write_artifact(
    path: str | os.PathLike[str],
    data: bytes,
    *,
    expected_sha256: str | None = None,
    mode: int = 0o644,
) -> ArtifactInfo:
    """Verify optional expected content, atomically persist it, and return metadata."""

    digest = sha256_bytes(data)
    if expected_sha256 is not None and not hmac.compare_digest(
        digest, expected_sha256.strip().casefold()
    ):
        raise ValueError("Artifact SHA-256 does not match the expected digest")
    destination = atomic_write_bytes(path, data, mode=mode)
    return ArtifactInfo(path=destination, sha256=digest, size=len(data))


def _sync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
