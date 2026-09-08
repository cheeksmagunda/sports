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


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    scraper = root / "scraper" / "storage_state.json"
    secrets = root / ".secrets"
    print(f"scraper_storage_state={'yes' if scraper.is_file() else 'no'}")
    if scraper.is_file():
        mode = oct(scraper.stat().st_mode & 0o777)
        print(f"scraper_storage_state_mode={mode}")
    sops_files = sorted(secrets.glob("*.sops.env")) if secrets.is_dir() else []
    print(f"sops_env_files={len(sops_files)}")
    for key in KEYS:
        print(f"{key}={'yes' if os.environ.get(key) else 'no'}")
    live_ready = scraper.is_file() or any(os.environ.get(k) for k in KEYS[:3])
    print(f"live_ingest_ready={'yes' if live_ready else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
