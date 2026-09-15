#!/usr/bin/env python3
"""Print presence-only Real Sports auth surface status (never values)."""

from __future__ import annotations

import os
from pathlib import Path

KEYS = (
    "REALSPORTS_STORAGE_STATE_B64GZ",
    "REALSPORTS_STORAGE_STATE_PATH",
    "NFL_REALSPORTS_STORAGE_STATE",
    "NFL_DEVICE_UUID",
    "NFL_DEVICE_NAME",
    "SOPS_AGE_KEY_FILE",
)

_PLACEHOLDERS = {
    "placeholder",
    "change-me",
    "changeme",
    "todo",
    "unused",
    "not-set",
}


def _candidate_storage_states() -> list[Path]:
    """Same durable/ephemeral order as ingest.realsports / auth_status."""

    paths: list[Path] = []
    for key in ("REALSPORTS_STORAGE_STATE_PATH", "NFL_REALSPORTS_STORAGE_STATE"):
        raw = os.environ.get(key, "").strip()
        if raw and not raw.startswith("{") and raw.lower() not in _PLACEHOLDERS:
            paths.append(Path(raw).expanduser())
    override = os.environ.get("NFL_ORACLE_SCRAPER_DIR", "").strip()
    if override:
        paths.append(Path(override).expanduser() / "storage_state.json")
    volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if volume:
        vol = Path(volume).expanduser()
        paths.append(vol / "scraper" / "storage_state.json")
        paths.append(vol / "storage_state.json")
    root = Path(__file__).resolve().parents[1]
    paths.append(root / "scraper" / "storage_state.json")
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file() and not path.is_symlink():
            return path
    return None


def _token_cache_exists() -> bool:
    override = (
        os.environ.get("REALSPORTS_TOKEN_CACHE_PATH", "").strip()
        or os.environ.get("NFL_REALSPORTS_TOKEN_CACHE", "").strip()
    )
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override).expanduser())
    scraper_override = os.environ.get("NFL_ORACLE_SCRAPER_DIR", "").strip()
    if scraper_override:
        candidates.append(Path(scraper_override).expanduser() / "request_token_cache.json")
    volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if volume:
        candidates.append(Path(volume).expanduser() / "scraper" / "request_token_cache.json")
    root = Path(__file__).resolve().parents[1]
    candidates.append(root / "scraper" / "request_token_cache.json")
    return any(path.is_file() and not path.is_symlink() for path in candidates)


def main() -> int:
    existing = _first_existing(_candidate_storage_states())
    print(f"scraper_storage_state={'yes' if existing is not None else 'no'}")
    if existing is not None:
        mode = oct(existing.stat().st_mode & 0o777)
        print(f"scraper_storage_state_mode={mode}")
        print(f"scraper_storage_state_path={existing}")
    print(f"token_cache_exists={'yes' if _token_cache_exists() else 'no'}")
    root = Path(__file__).resolve().parents[1]
    secrets = root / ".secrets"
    sops_files = sorted(secrets.glob("*.sops.env")) if secrets.is_dir() else []
    print(f"sops_env_files={len(sops_files)}")
    for key in KEYS:
        print(f"{key}={'yes' if os.environ.get(key) else 'no'}")
    live_ready = existing is not None or any(os.environ.get(k) for k in KEYS[:3])
    print(f"live_ingest_ready={'yes' if live_ready else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
