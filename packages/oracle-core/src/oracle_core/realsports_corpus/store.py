"""Append-only JSON artifact writes for the Real Sports corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from oracle_core.artifacts import atomic_write_json, sha256_bytes
from oracle_core.realsports_corpus.layout import (
    ArtifactName,
    SportCode,
    artifact_path,
)
from oracle_core.realsports_corpus.manifest import upsert_coverage_entry


def artifact_sha256(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(body)


def write_json_artifact(
    corpus_root: Path,
    *,
    sport: SportCode,
    season: str,
    slate_or_game_id: str,
    artifact: ArtifactName,
    payload: dict[str, Any],
) -> tuple[Path, str, int, bool]:
    """Write artifact JSON; return (path, sha256, bytes, wrote).

    Idempotent: if an existing file has the same sha256, skip rewrite.
    """

    rel = artifact_path(
        sport=sport,
        season=season,
        slate_or_game_id=slate_or_game_id,
        artifact=artifact,
    )
    target = corpus_root / rel
    # Match atomic_write_json serialization so idempotent checks compare equal.
    body = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")
    digest = sha256_bytes(body)
    wrote = True
    if target.is_file() and sha256_bytes(target.read_bytes()) == digest:
        wrote = False
    if wrote:
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(target, payload)
        body = target.read_bytes()
        digest = sha256_bytes(body)
    return target, digest, len(body), wrote


def append_artifact(
    corpus_root: Path,
    *,
    sport: SportCode,
    season: str,
    slate_or_game_id: str,
    artifact: ArtifactName,
    payload: dict[str, Any],
    source: str,
    scraped_at: str | None = None,
) -> dict[str, Any]:
    """Write one artifact and upsert coverage; return a value-free summary."""

    path, digest, byte_len, wrote = write_json_artifact(
        corpus_root,
        sport=sport,
        season=season,
        slate_or_game_id=slate_or_game_id,
        artifact=artifact,
        payload=payload,
    )
    rel = str(
        artifact_path(
            sport=sport,
            season=season,
            slate_or_game_id=slate_or_game_id,
            artifact=artifact,
        )
    ).replace("\\", "/")
    upsert_coverage_entry(
        corpus_root,
        sport=sport,
        season=season,
        slate_or_game_id=slate_or_game_id,
        artifact=artifact,
        relative_path=rel,
        sha256=digest,
        byte_len=byte_len,
        source=source,
        scraped_at=scraped_at,
    )
    return {
        "sport": sport,
        "season": season,
        "slate_or_game_id": slate_or_game_id,
        "artifact": artifact,
        "path": rel,
        "sha256_12": digest[:12],
        "bytes": byte_len,
        "wrote": wrote,
    }
