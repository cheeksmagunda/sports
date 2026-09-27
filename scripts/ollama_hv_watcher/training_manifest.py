"""Load the HV/TDV training-data inventory for the Ollama watcher (#574)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST_PATH = PACKAGE_DIR / "training_data_manifest.json"
REQUIRED_TOP_KEYS = (
    "schema_version",
    "issue",
    "objective",
    "sources",
    "calendars",
    "gate",
)


def load_training_data_manifest(
    path: Path | None = None,
) -> dict[str, Any]:
    """Return the training-data manifest object (validated lightly)."""

    manifest_path = Path(path) if path is not None else DEFAULT_MANIFEST_PATH
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"training_data_manifest_must_be_object:{manifest_path}")
    missing = [key for key in REQUIRED_TOP_KEYS if key not in raw]
    if missing:
        raise ValueError(f"training_data_manifest_missing_keys:{missing}")
    version = raw["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("training_data_manifest_schema_version_invalid")
    issue = raw["issue"]
    if isinstance(issue, bool) or not isinstance(issue, int) or issue != 574:
        raise ValueError("training_data_manifest_issue_must_be_574")
    sources = raw["sources"]
    if not isinstance(sources, list) or not sources:
        raise ValueError("training_data_manifest_sources_required")
    seen: set[str] = set()
    for row in sources:
        if not isinstance(row, dict) or not row.get("id"):
            raise ValueError("training_data_manifest_source_requires_id")
        source_id = str(row["id"])
        if source_id in seen:
            raise ValueError(f"training_data_manifest_duplicate_source_id:{source_id}")
        seen.add(source_id)
    return raw


def source_ids(manifest: dict[str, Any] | None = None) -> tuple[str, ...]:
    payload = manifest if manifest is not None else load_training_data_manifest()
    return tuple(str(row["id"]) for row in payload["sources"])
