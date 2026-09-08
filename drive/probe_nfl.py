"""Ad-hoc NFL endpoint probe, reusing WNBA Oracle's Real Sports auth machinery.

Read-only investigation script (not part of any application). Dumps raw JSON
bodies for NFL endpoints to drive/nfl_fixtures/ for the endpoint archaeology
report. Does not touch wnba-oracle app code or commit anything.

Usage (from repo root, with wnba-oracle's venv active):
    uv run --package wnba-oracle python drive/probe_nfl.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "wnba-oracle" / "src"))

from wnba_oracle.ingest.realsports import (  # noqa: E402
    BASE,
    StorageStateMissing,
    StorageStateStale,
    _http_headers,
    headers_or_capture,
)

OUT_DIR = REPO_ROOT / "drive" / "nfl_fixtures"


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    device_uuid = str(uuid.uuid4())
    try:
        headers = await headers_or_capture(device_uuid, "nfl-probe-01")
    except StorageStateMissing as exc:
        print(f"[BLOCK] {exc}", file=sys.stderr)
        return 78
    except StorageStateStale as exc:
        print(f"[BLOCK] {exc}", file=sys.stderr)
        return 78

    h = _http_headers(headers)
    timeout = httpx.Timeout(20.0, connect=10.0)

    targets = [
        ("home_next", f"{BASE}/home/nfl/next", {"cohort": 0}),
        ("boostcontrol", f"{BASE}/home/nfl/boostcontrol", {"cohort": 0}),
        ("squads", f"{BASE}/squads", {"sport": "nfl"}),
        ("game_19457_feed", f"{BASE}/games/19457/sport/nfl/feed",
         {"version": 2, "view": "recent", "viewFrame": "default"}),
        ("game_19457_stats", f"{BASE}/games/19457/sport/nfl/stats", {}),
        ("search_a", f"{BASE}/players/sport/nfl/search",
         {"query": "a", "searchType": "ratingLineup"}),
    ]

    async with httpx.AsyncClient(timeout=timeout) as client:
        for name, url, params in targets:
            print(f"GET {url} params={params}")
            try:
                r = await client.get(url, headers=h, params=params)
            except Exception as exc:
                print(f"  [ERR] {exc}", file=sys.stderr)
                continue
            out = OUT_DIR / f"{name}.json"
            out.write_text(r.text)
            print(f"  -> status={r.status_code} bytes={len(r.text)} -> {out.relative_to(REPO_ROOT)}")

    print("\nprobe done.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
