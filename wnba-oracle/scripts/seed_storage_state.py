"""Materialize the Playwright storage_state.json from a base64+gzip env var.

The cron container reads `REALSPORTS_STORAGE_STATE_B64GZ` (set on Railway)
and writes `scraper/storage_state.json` before Playwright starts. Without
this seed the first cron tick of a fresh container would have no cookie
context and re-auth would fail.

If the env var is empty (initial deploy, or after a manual clear), the
script no-ops with exit 0; the headless login flow handles cold start by
posting REAL_SPORTS_USERNAME + REAL_SPORTS_PASSWORD.
"""

from __future__ import annotations

import base64
import gzip
import os
import pathlib
import sys


def main() -> int:
    b64 = os.environ.get("REALSPORTS_STORAGE_STATE_B64GZ", "").strip()
    target = pathlib.Path(__file__).resolve().parents[1] / "scraper" / "storage_state.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not b64:
        print("seed_storage_state: env var empty; nothing to seed (cold start path)")
        return 0
    try:
        raw = gzip.decompress(base64.b64decode(b64))
    except Exception as exc:
        print(f"seed_storage_state: decode failed ({exc}); falling back to cold start", file=sys.stderr)
        return 0
    target.write_bytes(raw)
    print(f"seed_storage_state: wrote {target} ({len(raw)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
