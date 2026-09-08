from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "wnba-oracle" / "src"))

from wnba_oracle.ingest.realsports import BASE, _http_headers, headers_or_capture  # noqa: E402


async def main() -> None:
    headers = await headers_or_capture("nfl-probe-04", "nfl-probe-04")
    h = _http_headers(headers)
    async with httpx.AsyncClient(timeout=20.0) as client:
        for cid in range(2120, 2145):
            r = await client.get(
                f"{BASE}/games/playerratingcontest/{cid}",
                headers=h,
                params={"contestType": "sport", "source": "home"},
            )
            if r.status_code == 200:
                d = json.loads(r.text)
                c = d.get("info", {}).get("contest", {})
                print(cid, r.status_code, c.get("sport"), c.get("day"))
            else:
                print(cid, r.status_code)


if __name__ == "__main__":
    asyncio.run(main())
