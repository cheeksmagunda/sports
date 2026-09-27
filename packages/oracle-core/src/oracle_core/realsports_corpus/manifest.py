"""Coverage manifest for the Real Sports history corpus (issue #526)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from oracle_core.artifacts import atomic_write_json
from oracle_core.realsports_corpus.layout import ARTIFACT_NAMES, ArtifactName, SportCode

COVERAGE_MANIFEST_RELPATH = Path("coverage") / "manifest.json"
MANIFEST_SCHEMA_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class CoverageEntry:
    """One slate/game directory's captured artifacts."""

    sport: SportCode
    season: str
    slate_or_game_id: str
    artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    label: str = "total_value_leaderboard"
    notes: str = ""

    def key(self) -> str:
        return f"{self.sport}/{self.season}/{self.slate_or_game_id}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CoverageManifest:
    """Root coverage document: gaps are keys missing expected artifacts."""

    schema_version: int = MANIFEST_SCHEMA_VERSION
    updated_at: str = ""
    entries: dict[str, CoverageEntry] = field(default_factory=dict)
    expected_artifacts: tuple[str, ...] = ARTIFACT_NAMES

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "updated_at": self.updated_at or utc_now_iso(),
            "expected_artifacts": list(self.expected_artifacts),
            "entry_count": len(self.entries),
            "entries": {k: v.to_dict() for k, v in sorted(self.entries.items())},
            "gaps": self.gap_report(),
        }

    def gap_report(self) -> list[dict[str, Any]]:
        gaps: list[dict[str, Any]] = []
        for key, entry in sorted(self.entries.items()):
            missing = [
                name
                for name in self.expected_artifacts
                if name not in entry.artifacts
            ]
            if missing:
                gaps.append(
                    {
                        "key": key,
                        "sport": entry.sport,
                        "season": entry.season,
                        "slate_or_game_id": entry.slate_or_game_id,
                        "missing_artifacts": missing,
                    }
                )
        return gaps


def load_coverage_manifest(corpus_root: Path) -> CoverageManifest:
    path = corpus_root / COVERAGE_MANIFEST_RELPATH
    if not path.is_file():
        return CoverageManifest()
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries: dict[str, CoverageEntry] = {}
    for key, value in (raw.get("entries") or {}).items():
        if not isinstance(value, dict):
            continue
        entries[key] = CoverageEntry(
            sport=value["sport"],
            season=str(value["season"]),
            slate_or_game_id=str(value["slate_or_game_id"]),
            artifacts=dict(value.get("artifacts") or {}),
            label=str(value.get("label") or "total_value_leaderboard"),
            notes=str(value.get("notes") or ""),
        )
    expected = tuple(raw.get("expected_artifacts") or ARTIFACT_NAMES)
    return CoverageManifest(
        schema_version=int(raw.get("schema_version") or MANIFEST_SCHEMA_VERSION),
        updated_at=str(raw.get("updated_at") or ""),
        entries=entries,
        expected_artifacts=expected,  # type: ignore[arg-type]
    )


def write_coverage_manifest(corpus_root: Path, manifest: CoverageManifest) -> Path:
    manifest.updated_at = utc_now_iso()
    path = corpus_root / COVERAGE_MANIFEST_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, manifest.to_dict())
    return path


def upsert_coverage_entry(
    corpus_root: Path,
    *,
    sport: SportCode,
    season: str,
    slate_or_game_id: str,
    artifact: ArtifactName,
    relative_path: str,
    sha256: str,
    byte_len: int,
    source: str,
    scraped_at: str | None = None,
) -> CoverageManifest:
    """Record one artifact on the coverage manifest (append-friendly)."""

    manifest = load_coverage_manifest(corpus_root)
    key = f"{sport}/{season}/{slate_or_game_id}"
    entry = manifest.entries.get(key) or CoverageEntry(
        sport=sport,
        season=season,
        slate_or_game_id=slate_or_game_id,
    )
    entry.artifacts[artifact] = {
        "path": relative_path,
        "sha256": sha256,
        "bytes": byte_len,
        "source": source,
        "scraped_at": scraped_at or utc_now_iso(),
    }
    manifest.entries[key] = entry
    write_coverage_manifest(corpus_root, manifest)
    return manifest
