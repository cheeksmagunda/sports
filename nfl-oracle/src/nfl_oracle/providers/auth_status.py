"""Report Real Sports auth presence without printing secret values."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from nfl_oracle.common.paths import resolve_project_root


@dataclass(frozen=True)
class AuthProbeResult:
    """Path/env presence only. Never includes secret material."""

    usable: bool
    storage_state_path: str | None
    storage_state_exists: bool
    env_path_set: bool
    env_b64gz_set: bool
    device_uuid_set: bool
    device_name_set: bool
    token_cache_exists: bool
    sibling_wnba_storage_exists: bool
    notes: tuple[str, ...]

    def to_json_obj(self) -> dict[str, Any]:
        return asdict(self)


def _project_root() -> Path:
    return resolve_project_root(__file__)


def _candidate_storage_paths() -> list[Path]:
    paths: list[Path] = []
    for key in ("REALSPORTS_STORAGE_STATE_PATH", "NFL_REALSPORTS_STORAGE_STATE"):
        raw = os.environ.get(key, "").strip()
        if raw:
            paths.append(Path(raw).expanduser())
    root = _project_root()
    paths.append(root / "scraper" / "storage_state.json")
    paths.append(root.parent / "wnba-oracle" / "scraper" / "storage_state.json")
    # de-dupe while preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def probe_realsports_auth() -> AuthProbeResult:
    """Offline probe: does not open browsers, mint tokens, or print secrets."""

    env_path_set = bool(
        os.environ.get("REALSPORTS_STORAGE_STATE_PATH", "").strip()
        or os.environ.get("NFL_REALSPORTS_STORAGE_STATE", "").strip()
    )
    env_b64gz_set = bool(os.environ.get("REALSPORTS_STORAGE_STATE_B64GZ", "").strip())
    device_uuid_set = bool(
        os.environ.get("NFL_DEVICE_UUID", "").strip()
        or os.environ.get("WNBA_DEVICE_UUID", "").strip()
    )
    device_name_set = bool(
        os.environ.get("NFL_DEVICE_NAME", "").strip()
        or os.environ.get("WNBA_DEVICE_NAME", "").strip()
    )

    existing: Path | None = None
    for candidate in _candidate_storage_paths():
        if candidate.is_file() and not candidate.is_symlink():
            existing = candidate
            break

    root = _project_root()
    sibling = root.parent / "wnba-oracle" / "scraper" / "storage_state.json"
    token_cache = root / "scraper" / "request_token_cache.json"
    sibling_token = root.parent / "wnba-oracle" / "scraper" / "request_token_cache.json"
    token_cache_exists = (token_cache.is_file() and not token_cache.is_symlink()) or (
        sibling_token.is_file() and not sibling_token.is_symlink()
    )

    notes: list[str] = []
    if existing is None and not env_b64gz_set:
        notes.append("no_storage_state_on_disk_or_b64gz_env")
    if not device_uuid_set:
        notes.append("NFL_DEVICE_UUID_unset_will_use_dev_default")
    if existing is not None:
        notes.append("storage_state_path_present_contents_not_inspected")
    if env_b64gz_set:
        notes.append("REALSPORTS_STORAGE_STATE_B64GZ_set_not_materialized")

    usable = existing is not None or env_b64gz_set
    return AuthProbeResult(
        usable=usable,
        storage_state_path=str(existing) if existing is not None else None,
        storage_state_exists=existing is not None,
        env_path_set=env_path_set,
        env_b64gz_set=env_b64gz_set,
        device_uuid_set=device_uuid_set,
        device_name_set=device_name_set,
        token_cache_exists=token_cache_exists,
        sibling_wnba_storage_exists=sibling.is_file() and not sibling.is_symlink(),
        notes=tuple(notes),
    )
