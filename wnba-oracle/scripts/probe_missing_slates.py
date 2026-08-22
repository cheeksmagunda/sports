"""Probe Real Sports contest_ids to find slates we are missing for the
2025 playoff window (Sept 18 -> Oct 11 2025) and the 2026 season-start
window (Apr 25 -> May 3 2026).

Strategy:
  1. Try cached headers from scraper/request_token_cache.json (ignoring
     the 30-min TTL -- the underlying token usually lives longer). Hit
     a known-good neighbor contest_id to verify auth.
  2. If 401, refresh via Playwright (capture_live_headers; relies on
     scraper/storage_state.json being usable).
  3. Walk contest_ids in three windows where the gap is suspected:
       - 878 .. 1000   (after last 2025 regular-season slate cid=877)
       - 1400 .. 1500  (probable 2026 preseason / start)
       - 1500 .. 1755  (between probable preseason and confirmed 2026 cid=1755)
     For each cid: GET /stats. Record sport, day, status.
  4. Cross-reference returned (sport='wnba', day in missing_dates) and
     print a summary the operator (or the next script) can act on.

Output: prints a CSV-ish summary; persists nothing.
"""

from __future__ import annotations

import asyncio
import csv
import json
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

CACHE = REPO / "scraper" / "request_token_cache.json"

# Game-days that have wnba_game_logs rows but no slate_labels row.
MISSING_SLATE_DATES = {
    "2025-09-18",
    "2025-09-19",
    "2025-09-21",
    "2025-09-23",
    "2025-09-26",
    "2025-09-28",
    "2025-09-30",
    "2025-10-03",
    "2025-10-05",
    "2025-10-08",
    "2025-10-10",
    "2026-04-25",
    "2026-04-26",
    "2026-04-27",
    "2026-04-29",
    "2026-04-30",
    "2026-05-01",
    "2026-05-02",
    "2026-05-03",
}

WINDOWS = [
    (878, 1000),  # after the last confirmed 2025 reg-season slate (cid 877)
    (1400, 1500),  # probable 2026 preseason window
    (1500, 1755),  # gap between preseason and first confirmed 2026 slate
]

OUT_CSV = Path("/tmp/wnba_missing_slates_probe.csv")


def _cached_http_headers() -> dict[str, str]:
    """Build request headers from the cache file, regardless of TTL."""
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


async def _refresh_via_playwright() -> dict[str, str]:
    from wnba_oracle.ingest.realsports import _http_headers, capture_live_headers

    uuid = json.loads(CACHE.read_text())["real-device-uuid"]
    name = json.loads(CACHE.read_text()).get("real-device-name", "wnba-oracle-prod-01")
    h = await capture_live_headers(uuid, name)
    return _http_headers(h)


def _probe_one(client: httpx.Client, headers: dict[str, str], cid: int) -> dict:
    url = f"https://web.realapp.com/games/playerratingcontest/{cid}/stats"
    try:
        r = client.get(url, headers=headers, timeout=15.0)
    except Exception as exc:
        return {"cid": cid, "status": "EXC", "sport": "", "day": "", "err": str(exc)[:80]}
    if r.status_code != 200:
        return {"cid": cid, "status": str(r.status_code), "sport": "", "day": "", "err": ""}
    try:
        body = r.json() or {}
    except Exception:
        return {"cid": cid, "status": "200_NONJSON", "sport": "", "day": "", "err": ""}
    contest = body.get("contest") or {}
    return {
        "cid": cid,
        "status": "200",
        "sport": str(contest.get("sport") or ""),
        "day": str(contest.get("day") or ""),
        "err": "",
    }


async def amain() -> int:
    if not CACHE.exists():
        print(f"no cached headers at {CACHE}; aborting", file=sys.stderr)
        return 2

    headers = _cached_http_headers()
    # Quick auth check with a known-good neighbor cid.
    with httpx.Client(timeout=15.0) as client:
        warmup = _probe_one(client, headers, 877)
        print(
            f"warmup cid=877 -> status={warmup['status']} sport={warmup['sport']} day={warmup['day']}"
        )
        if warmup["status"] in {"401", "EXC"}:
            print("cached headers stale; refreshing via Playwright (storage_state.json)...")
            headers = await _refresh_via_playwright()
            warmup = _probe_one(client, headers, 877)
            print(
                f"post-refresh warmup cid=877 -> status={warmup['status']} sport={warmup['sport']} day={warmup['day']}"
            )
            if warmup["status"] != "200":
                print(f"FATAL: still not authed (status={warmup['status']})", file=sys.stderr)
                return 3

        results: list[dict] = []
        hits_wnba: list[dict] = []
        hits_missing: list[dict] = []
        for lo, hi in WINDOWS:
            print(f"\n=== window cid {lo}..{hi} ===")
            for cid in range(lo, hi + 1):
                row = _probe_one(client, headers, cid)
                results.append(row)
                if row["sport"] == "wnba":
                    hits_wnba.append(row)
                    if row["day"] in MISSING_SLATE_DATES:
                        hits_missing.append(row)
                        print(f"  HIT cid={cid} day={row['day']} (MISSING-SLATE)")
                    else:
                        print(f"  wnba cid={cid} day={row['day']}")
                # tiny polite delay
                time.sleep(0.25)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cid", "status", "sport", "day", "err"])
        w.writeheader()
        w.writerows(results)
    print(
        f"\nWrote {OUT_CSV}: {len(results)} probes, "
        f"{len(hits_wnba)} wnba contests found, "
        f"{len(hits_missing)} match a missing-slate date."
    )
    if hits_missing:
        print("\nRecoverable missing slates:")
        for h in hits_missing:
            print(f"  cid={h['cid']} day={h['day']}")
    return 0


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
