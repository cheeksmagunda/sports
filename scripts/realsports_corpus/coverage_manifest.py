"""coverage_manifest schema and Ollama Codespace helper gate (#526).

Manifest path in the corpus repo: ``coverage_manifest.json`` (repo root).

Ollama on the Codespace is an internal smart training helper only after this
manifest shows complete historical capture of every required Real Sports
variable family. Until then the helper is FORBIDDEN.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from oracle_core.artifacts import atomic_write_json

from realsports_corpus.layout import (
    REQUIRED_VARIABLE_FAMILIES,
    SPORTS,
    Sport,
    VariableFamily,
)

SCHEMA_VERSION = 1
DEFAULT_CORPUS_REPO = "cheeksmagunda/sports-realsports-corpus"

FamilyStatus = Literal["present", "partial", "absent", "unknown", "stub"]


class OllamaForbiddenError(RuntimeError):
    """Raised when an Ollama Codespace helper is requested before coverage is complete."""


@dataclass(frozen=True)
class CoverageManifest:
    """In-memory view of ``coverage_manifest.json``."""

    payload: dict[str, Any]

    @property
    def schema_version(self) -> int:
        return int(self.payload.get("schema_version", 0))

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_empty_manifest(*, updated_at: str | None = None) -> CoverageManifest:
    """Empty portfolio gap matrix: every sport/family starts as ``unknown``."""

    sports: dict[str, Any] = {}
    for sport in SPORTS:
        sports[sport] = {
            "years": {},
            "families": {
                family: {"status": "unknown", "artifact_count": 0, "notes": []}
                for family in REQUIRED_VARIABLE_FAMILIES
            },
        }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": updated_at,
        "corpus_repo": DEFAULT_CORPUS_REPO,
        "description": (
            "Append-only coverage matrix for Real Sports history ingest. "
            "Soft-merge unions only; never delete keys from scheduled appends."
        ),
        "status_enum": ["present", "partial", "absent", "unknown", "stub"],
        "kinds": list(REQUIRED_VARIABLE_FAMILIES),
        "historical_capture_complete": False,
        "ollama_codespace_helper": {
            "allowed": False,
            "policy": (
                "FORBIDDEN until coverage_manifest.historical_capture_complete "
                "is true for every required Real Sports variable family across "
                "every historical slate represented in this corpus."
            ),
        },
        "required_families": list(REQUIRED_VARIABLE_FAMILIES),
        "sports": sports,
    }
    return CoverageManifest(payload)


def record_family_status(
    manifest: CoverageManifest,
    *,
    sport: Sport,
    family: VariableFamily,
    status: FamilyStatus,
    artifact_count: int = 0,
    note: str | None = None,
    year: int | None = None,
    slate_date: str | None = None,
    sha256: str | None = None,
) -> CoverageManifest:
    """Return a new manifest with one family (and optional slate cell) updated."""

    payload = _deep_copy(manifest.payload)
    sport_block = payload["sports"].setdefault(sport, {"years": {}, "families": {}})
    family_block = sport_block["families"].setdefault(
        family, {"status": "unknown", "artifact_count": 0, "notes": []}
    )
    family_block["status"] = status
    family_block["artifact_count"] = int(artifact_count)
    if note:
        notes = list(family_block.get("notes") or [])
        if note not in notes:
            notes.append(note)
        family_block["notes"] = notes

    if year is not None and slate_date is not None:
        year_block = sport_block["years"].setdefault(str(year), {"slates": {}})
        slate_block = year_block["slates"].setdefault(
            slate_date, {"status": "partial", "kinds": {}, "labels": []}
        )
        kind_meta: dict[str, Any] = {
            "status": status,
            "artifact_count": int(artifact_count),
        }
        if sha256:
            kind_meta["sha256"] = sha256
        kinds = slate_block.setdefault("kinds", {})
        kinds[family] = kind_meta
        present = sum(1 for meta in kinds.values() if meta.get("status") == "present")
        if present >= len(REQUIRED_VARIABLE_FAMILIES):
            slate_block["status"] = "present"
        elif present:
            slate_block["status"] = "partial"
        else:
            slate_block["status"] = "absent"
        if note:
            labels = slate_block.setdefault("labels", [])
            if note not in labels:
                labels.append(note)

    payload["updated_at"] = _utc_now()
    payload["historical_capture_complete"] = _compute_complete(payload)
    helper = payload.setdefault("ollama_codespace_helper", {"allowed": False})
    helper["allowed"] = bool(payload["historical_capture_complete"])
    return CoverageManifest(payload)


def _compute_complete(payload: Mapping[str, Any]) -> bool:
    """Complete only when every sport reports every required family as present."""

    sports = payload.get("sports")
    if not isinstance(sports, dict):
        return False
    for sport in SPORTS:
        block = sports.get(sport)
        if not isinstance(block, dict):
            return False
        families = block.get("families")
        if not isinstance(families, dict):
            return False
        for family in REQUIRED_VARIABLE_FAMILIES:
            entry = families.get(family)
            if not isinstance(entry, dict) or entry.get("status") != "present":
                return False
            if int(entry.get("artifact_count") or 0) < 1:
                return False
    return True


def is_historical_capture_complete(manifest: CoverageManifest) -> bool:
    if bool(manifest.payload.get("historical_capture_complete")):
        return True
    return _compute_complete(manifest.payload)


def ollama_helper_allowed(manifest: CoverageManifest) -> bool:
    return is_historical_capture_complete(manifest)


def assert_ollama_helper_forbidden(manifest: CoverageManifest) -> None:
    """Hard gate: raise unless coverage_manifest shows complete capture."""

    if ollama_helper_allowed(manifest):
        return
    raise OllamaForbiddenError(
        "Ollama Codespace helper is FORBIDDEN until coverage_manifest shows "
        "complete historical variable capture "
        f"(required families: {', '.join(REQUIRED_VARIABLE_FAMILIES)})."
    )


def coverage_manifest_path(corpus_root: Path) -> Path:
    return Path(corpus_root) / "coverage_manifest.json"


def write_coverage_manifest(path: Path, manifest: CoverageManifest) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, manifest.to_dict())
    return path


def load_coverage_manifest(path: Path) -> CoverageManifest:
    import json

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("coverage_manifest must be a JSON object")
    return CoverageManifest(raw)


def _deep_copy(value: Any) -> Any:
    import copy

    return copy.deepcopy(value)
