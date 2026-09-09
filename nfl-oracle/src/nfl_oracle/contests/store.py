"""Resumable, content-addressed persistence for the Corpus C contest archive.

Layout under ``data/raw/corpus_c``::

    <contest_id>/meta.json           + meta.json.provenance.json
    <contest_id>/draftinfo.json      + ...
    <contest_id>/entries.json
    <contest_id>/stats.json
    <contest_id>/payoutinfo.json
    <contest_id>/manifest.json

The scan cursor lives in ``data/catalog/corpus_c_cursor.json`` so a run that is
interrupted resumes without refetching. Payloads are redacted before they touch
disk and every write is atomic.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from oracle_core.artifacts import atomic_write_bytes, atomic_write_json, sha256_bytes

from nfl_oracle.common.paths import resolve_project_root
from nfl_oracle.ingest.redact import assert_no_identity_leak, redact_corpus_payload

RouteName = Literal["meta", "draftinfo", "entries", "stats", "payoutinfo"]

ROUTE_FILENAMES: dict[RouteName, str] = {
    "meta": "meta.json",
    "draftinfo": "draftinfo.json",
    "entries": "entries.json",
    "stats": "stats.json",
    "payoutinfo": "payoutinfo.json",
}

# Sub-routes fetched only for contests whose meta says sport == nfl.
NFL_SUB_ROUTES: tuple[RouteName, ...] = ("draftinfo", "entries", "stats", "payoutinfo")


def project_root(override: Path | None = None) -> Path:
    return Path(override).resolve() if override is not None else resolve_project_root(__file__)


def corpus_c_root(override: Path | None = None) -> Path:
    return project_root(override) / "data" / "raw" / "corpus_c"


def cursor_path(override: Path | None = None) -> Path:
    return project_root(override) / "data" / "catalog" / "corpus_c_cursor.json"


@dataclass(frozen=True)
class ContestProvenance:
    contest_id: int
    route: RouteName
    source_url: str
    http_status: int
    content_sha256: str
    captured_at: str
    byte_len: int
    redacted: bool = True
    # ``day`` is the provider's own contest day, the only clock a contest has.
    contest_day: str | None = None
    sport: str | None = None
    is_finalized: bool | None = None


@dataclass
class ScanCursor:
    """Durable record of which contest ids have been resolved and how."""

    # Highest id examined, so a resumed scan knows where it stopped.
    highest_examined: int = 0
    # ids whose meta returned 200 and sport == nfl, fully collected.
    nfl_collected: list[int] = field(default_factory=list)
    # ids whose meta returned 200 for some other sport. Cheap to skip forever.
    other_sport: dict[str, str] = field(default_factory=dict)
    # ids the provider refused or does not have. Absent, not empty.
    absent: dict[str, int] = field(default_factory=dict)
    # ids that failed for a transient reason and should be retried.
    failed: dict[str, str] = field(default_factory=dict)
    updated_at: str = ""
    contest_entry: Literal[False] = False

    @classmethod
    def load(cls, path: Path) -> ScanCursor:
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            highest_examined=int(raw.get("highest_examined", 0)),
            nfl_collected=[int(x) for x in raw.get("nfl_collected", [])],
            other_sport={str(k): str(v) for k, v in (raw.get("other_sport") or {}).items()},
            absent={str(k): int(v) for k, v in (raw.get("absent") or {}).items()},
            failed={str(k): str(v) for k, v in (raw.get("failed") or {}).items()},
            updated_at=str(raw.get("updated_at", "")),
        )

    def save(self, path: Path) -> None:
        self.updated_at = datetime.now(UTC).isoformat()
        self.nfl_collected = sorted(set(self.nfl_collected))
        atomic_write_json(path, asdict(self), mode=0o600)

    def resolved(self) -> set[int]:
        """ids that need no further meta request."""
        return (
            set(self.nfl_collected)
            | {int(k) for k in self.other_sport}
            | {int(k) for k in self.absent}
        )

    def pending(self, ids: Iterable[int], *, retry_failed: bool = True) -> list[int]:
        done = self.resolved()
        if not retry_failed:
            done |= {int(k) for k in self.failed}
        return [i for i in ids if i not in done]


class ContestStore:
    """Writes redacted contest payloads with integrity sidecars."""

    def __init__(self, root: Path | None = None, *, project: Path | None = None) -> None:
        self.root = Path(root) if root is not None else corpus_c_root(project)

    def contest_dir(self, contest_id: int) -> Path:
        return self.root / str(contest_id)

    def write_route(
        self,
        contest_id: int,
        route: RouteName,
        payload: Mapping[str, Any],
        *,
        source_url: str,
        http_status: int,
        captured_at: datetime,
        contest_day: str | None = None,
        sport: str | None = None,
        is_finalized: bool | None = None,
    ) -> ContestProvenance:
        clean = redact_corpus_payload(dict(payload))
        assert_no_identity_leak(clean)
        encoded = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode()
        target = self.contest_dir(contest_id) / ROUTE_FILENAMES[route]
        provenance = ContestProvenance(
            contest_id=contest_id,
            route=route,
            source_url=source_url,
            http_status=http_status,
            content_sha256=sha256_bytes(encoded),
            captured_at=captured_at.isoformat(),
            byte_len=len(encoded),
            contest_day=contest_day,
            sport=sport,
            is_finalized=is_finalized,
        )
        atomic_write_bytes(target, encoded, mode=0o600)
        atomic_write_json(
            target.with_suffix(".json.provenance.json"), asdict(provenance), mode=0o600
        )
        return provenance

    def write_manifest(
        self, contest_id: int, provenances: Iterable[ContestProvenance], **extra: Any
    ) -> Path:
        rows = [asdict(p) for p in provenances]
        manifest = {
            "contest_id": contest_id,
            "routes": rows,
            "collected_at": datetime.now(UTC).isoformat(),
            "contest_entry": False,
            "read_only": True,
            **extra,
        }
        path = self.contest_dir(contest_id) / "manifest.json"
        atomic_write_json(path, manifest, mode=0o600)
        return path

    def has_route(self, contest_id: int, route: RouteName) -> bool:
        return (self.contest_dir(contest_id) / ROUTE_FILENAMES[route]).exists()

    def read_route(self, contest_id: int, route: RouteName) -> dict[str, Any] | None:
        path = self.contest_dir(contest_id) / ROUTE_FILENAMES[route]
        if not path.exists():
            return None
        provenance_path = path.with_suffix(".json.provenance.json")
        data = path.read_bytes()
        if provenance_path.exists():
            expected = json.loads(provenance_path.read_text(encoding="utf-8"))["content_sha256"]
            if sha256_bytes(data) != expected:
                raise ValueError(f"corpus_c_integrity:{contest_id}:{route}")
        loaded = json.loads(data.decode())
        return loaded if isinstance(loaded, dict) else None

    def collected_ids(self) -> list[int]:
        if not self.root.exists():
            return []
        return sorted(
            int(p.name)
            for p in self.root.iterdir()
            if p.is_dir() and p.name.isdigit() and (p / "meta.json").exists()
        )
