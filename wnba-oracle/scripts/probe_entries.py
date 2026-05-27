"""Deeper probe of /entries endpoint on the finalized WNBA contest from
2026-05-25 (cid=1831 per probe_leaderboard.py walk). Also tries variant
URL forms to understand what /entries actually returns."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

import httpx

OUT_DIR = Path("/tmp/wnba-probes")
OUT_DIR.mkdir(parents=True, exist_ok=True)


async def amain():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from wnba_oracle.ingest.realsports import (
        BASE,
        _http_headers,
        headers_or_capture,
    )

    device_uuid = os.environ.get("WNBA_DEVICE_UUID") or str(uuid.uuid4())
    headers_obj = await headers_or_capture(device_uuid, "wnba-oracle-probe-02")
    h = _http_headers(headers_obj)

    targets = [
        # 2026-05-25 wnba finalized contest
        ("1831", "/games/playerratingcontest/1831/entries"),
        ("1831_top20", "/games/playerratingcontest/1831/entries?cohort=top_20"),
        ("1831_limit50", "/games/playerratingcontest/1831/entries?limit=50"),
        ("1831_page1", "/games/playerratingcontest/1831/entries?page=1"),
        ("1831_first10", "/games/playerratingcontest/1831/entries?first=10"),
        # Also try /leaderboard variants on a finalized contest
        ("1831_lb", "/games/playerratingcontest/1831/leaderboard"),
        # 2026-05-24 wnba
        ("1829", "/games/playerratingcontest/1829/entries"),
        # And /stats on the same to confirm sport
        ("1831_stats", "/games/playerratingcontest/1831/stats"),
    ]

    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for label, path in targets:
            url = BASE + path
            r = await client.get(url, headers=h, timeout=15.0)
            print(f"\n=== {label} ({r.status_code}) {path}")
            (OUT_DIR / f"entries_{label}.json").write_text(r.text)
            if r.status_code == 200:
                try:
                    data = r.json()
                    if isinstance(data, dict):
                        print(f"  keys: {sorted(data.keys())}")
                        contest = data.get("contest") or {}
                        if contest:
                            print(
                                f"  contest.sport={contest.get('sport')}, "
                                f"day={contest.get('day')}, "
                                f"final={contest.get('isFinalized')}"
                            )
                        entries = data.get("entries")
                        if entries is not None:
                            print(f"  entries count: {len(entries)}")
                            if entries:
                                print(f"  entries[0] keys: {sorted(entries[0].keys()) if isinstance(entries[0], dict) else type(entries[0]).__name__}")
                                print(f"  entries[0] sample: {json.dumps(entries[0], indent=2)[:1500]}")
                    elif isinstance(data, list):
                        print(f"  list of {len(data)}")
                        if data:
                            print(f"  [0]: {json.dumps(data[0], indent=2)[:1000]}")
                except Exception as exc:
                    print(f"  parse error: {exc}")
            await asyncio.sleep(0.4)

    print("\nDone. See /tmp/wnba-probes/entries_*.json")


if __name__ == "__main__":
    asyncio.run(amain())
