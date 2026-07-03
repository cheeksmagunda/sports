"""Coarse-stride probe of contest_ids 1..571 to find any WNBA contests
that pre-date our scraped corpus floor (first slate is cid=572 on
2025-05-16).

If we find WNBA hits, the pattern of cids will tell us whether to
expand to stride=1 for full recovery. If we find NONE, that confirms
the Real Sports WNBA contest launched at cid=572 and there is no
2024 / early-2025 backfill available.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

CACHE = REPO / "scraper" / "request_token_cache.json"


def _http_headers_from_cache() -> dict[str, str]:
    raw = json.loads(CACHE.read_text())
    return {
        "real-request-token": raw["real-request-token"],
        "real-version": raw.get("real-version", "31"),
        "real-device-type": raw.get("real-device-type", "desktop_web"),
        "real-device-uuid": raw["real-device-uuid"],
        "real-device-id": raw.get("real-device-id", raw["real-device-uuid"]),
        "real-device-name": raw.get("real-device-name", "wnba-oracle-prod-01"),
        "user-agent": raw.get("user-agent", ""),
        "accept": "application/json",
        "content-type": "application/json",
        "referer": "https://realsports.io/",
        "origin": "https://realsports.io",
        "real-auth-info": raw["real-auth-info"],
    }


async def _refresh() -> dict[str, str]:
    from wnba_oracle.ingest.realsports import _http_headers, capture_live_headers
    raw = json.loads(CACHE.read_text())
    h = await capture_live_headers(raw["real-device-uuid"], raw.get("real-device-name", "wnba-oracle-prod-01"))
    return _http_headers(h)


def _probe(client: httpx.Client, headers: dict[str, str], cid: int) -> tuple[int, str, str]:
    url = f"https://web.realapp.com/games/playerratingcontest/{cid}/stats"
    try:
        r = client.get(url, headers=headers, timeout=15.0)
    except Exception as exc:
        return -1, "EXC", str(exc)[:40]
    if r.status_code != 200:
        return r.status_code, "", ""
    try:
        body = r.json() or {}
    except Exception:
        return 200, "NON_JSON", ""
    contest = body.get("contest") or {}
    return 200, str(contest.get("sport") or ""), str(contest.get("day") or "")


async def amain() -> int:
    headers = _http_headers_from_cache()
    with httpx.Client(timeout=15.0) as client:
        s, sport, day = _probe(client, headers, 572)
        print(f"warmup cid=572 -> status={s} sport={sport} day={day}")
        if s == 401:
            print("refreshing headers...")
            headers = await _refresh()
            s, sport, day = _probe(client, headers, 572)
            print(f"post-refresh cid=572 -> status={s} sport={sport} day={day}")
            if s != 200:
                print("FATAL still not authed", file=sys.stderr)
                return 3

        # Coarse stride-3 sweep of cid 1..571.
        wnba_hits: list[tuple[int, str]] = []
        seen_sports: dict[str, int] = {}
        for cid in range(1, 572, 3):
            s, sport, day = _probe(client, headers, cid)
            seen_sports[sport] = seen_sports.get(sport, 0) + 1
            if sport == "wnba":
                wnba_hits.append((cid, day))
                print(f"  HIT cid={cid} day={day}")
            time.sleep(0.20)

    print("\n=== summary (cid 1..571, stride=3) ===")
    print(f"sports seen: {sorted(seen_sports.items(), key=lambda x: -x[1])}")
    print(f"wnba hits: {len(wnba_hits)}")
    if wnba_hits:
        print("first 10 wnba hits:")
        for h in wnba_hits[:10]:
            print(" ", h)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(amain()))
