"""Redacted NHL raw payload persistence with sidecar provenance.

Adapts nfl-oracle's ingest/corpus_g.py Provenance shape for NHL. The store
root must be passed explicitly (no project-root auto-detection): this
scaffold is exercised only against synthetic fixtures and test tmp_paths
until the Week 1 authorization checkpoint (issue #135) is separately granted
for real provider collection.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from oracle_core.artifacts import atomic_write_bytes, atomic_write_json, sha256_bytes

NhlEndpointName = Literal["boxscore", "roster", "contest"]

ENDPOINT_FILENAMES: dict[NhlEndpointName, str] = {
    "boxscore": "boxscore.json",
    "roster": "roster.json",
    "contest": "contest.json",
}


@dataclass(frozen=True)
class Provenance:
    game_id: int
    season: int | None
    endpoint: NhlEndpointName
    source_url: str
    content_sha256: str
    captured_at: str
    byte_len: int
    redacted: bool = True
    event_time: str | None = None
    source_available_at: str | None = None
    decision_at: str | None = None


@dataclass(frozen=True)
class StoredArtifact:
    path: Path
    provenance_path: Path
    provenance: Provenance
    wrote: bool


class NhlCorpusStore:
    """Filesystem store for redacted NHL raw payloads with sidecar provenance."""

    def __init__(self, root: Path) -> None:
        self.raw_root = Path(root) / "data" / "raw" / "corpus_nhl"
        self.raw_root.mkdir(parents=True, exist_ok=True)

    def game_dir(self, season: int | None, game_id: int) -> Path:
        season_key = str(season) if season is not None else "unknown"
        path = self.raw_root / season_key / str(game_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def persist_endpoint(
        self,
        *,
        game_id: int,
        season: int | None,
        endpoint: NhlEndpointName,
        payload: dict[str, Any],
        source_url: str,
        captured_at: str,
        event_time: str | None = None,
        source_available_at: str | None = None,
        decision_at: str | None = None,
    ) -> StoredArtifact:
        body = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        digest = sha256_bytes(body)
        prov = Provenance(
            game_id=game_id,
            season=season,
            endpoint=endpoint,
            source_url=source_url,
            content_sha256=digest,
            captured_at=captured_at,
            byte_len=len(body),
            event_time=event_time,
            source_available_at=source_available_at,
            decision_at=decision_at,
        )
        directory = self.game_dir(season, game_id)
        payload_path = directory / ENDPOINT_FILENAMES[endpoint]
        provenance_path = directory / f"{ENDPOINT_FILENAMES[endpoint]}.provenance.json"
        wrote = True
        if payload_path.is_file() and provenance_path.is_file():
            existing = json.loads(provenance_path.read_text(encoding="utf-8"))
            if existing.get("content_sha256") == digest:
                wrote = False
        if wrote:
            atomic_write_bytes(payload_path, body)
            atomic_write_json(provenance_path, asdict(prov))
        return StoredArtifact(
            path=payload_path,
            provenance_path=provenance_path,
            provenance=prov,
            wrote=wrote,
        )
