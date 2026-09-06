#!/usr/bin/env python3
"""Materialize scraper/storage_state.json from REALSPORTS_STORAGE_STATE_B64GZ."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfl_oracle.ingest.realsports import (  # noqa: E402
    StorageStateMissing,
    materialize_storage_state_from_env,
    storage_state_path,
)


def main() -> int:
    try:
        path = materialize_storage_state_from_env()
    except StorageStateMissing as exc:
        print(f"seed_storage_state: {exc}", file=sys.stderr)
        return 78
    if path is None:
        existing = storage_state_path()
        if existing.is_file():
            print(f"seed_storage_state: using existing {existing}")
            return 0
        print("seed_storage_state: derived session is not configured")
        return 0
    print("seed_storage_state: derived session materialized with mode 0600")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
