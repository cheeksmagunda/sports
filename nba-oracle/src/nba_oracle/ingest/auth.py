"""Presence-only Real Sports auth checks for NBA ingest (never print values)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Portfolio-wide Real Sports session (root AGENTS.md). NBA does not mint its own.
PORTFOLIO_STORAGE_STATE_KEYS = (
    "REALSPORTS_STORAGE_STATE_B64GZ",
    "REALSPORTS_STORAGE_STATE_PATH",
)

_PLACEHOLDERS = {
    "placeholder",
    "change-me",
    "changeme",
    "todo",
    "unused",
    "not-set",
}


@dataclass(frozen=True)
class AuthPresence:
    storage_state_env_present: bool
    storage_state_file_present: bool
    ready: bool
    blocked_reason: str | None


def _path_candidates() -> list[Path]:
    paths: list[Path] = []
    raw = os.environ.get("REALSPORTS_STORAGE_STATE_PATH", "").strip()
    if raw and not raw.startswith("{") and raw.lower() not in _PLACEHOLDERS:
        paths.append(Path(raw).expanduser())
    volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if volume:
        vol = Path(volume).expanduser()
        paths.append(vol / "scraper" / "storage_state.json")
        paths.append(vol / "storage_state.json")
    return paths


def auth_presence() -> AuthPresence:
    """Report whether shared Real Sports auth material is present (not valid)."""

    env_present = any(os.environ.get(key, "").strip() for key in PORTFOLIO_STORAGE_STATE_KEYS)
    file_present = any(path.is_file() and not path.is_symlink() for path in _path_candidates())
    ready = env_present or file_present
    reason = None if ready else "realsports_auth_unavailable"
    return AuthPresence(
        storage_state_env_present=env_present,
        storage_state_file_present=file_present,
        ready=ready,
        blocked_reason=reason,
    )
