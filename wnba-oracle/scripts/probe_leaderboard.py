"""Probe for the Real Sports WNBA leaderboard endpoint + verify historical
contest /stats access.

What this does:
  1. Refresh Playwright-captured auth headers (or reuse fresh cache).
  2. Hit a curated list of candidate leaderboard URLs against contest 1840
     (today's WNBA contest, per D18). Dumps every status + first 4KB of
     each response to /tmp/wnba-probes/ so the operator can pick out the
     endpoint that actually returns top-N finishers.
  3. Walk contest IDs 1840 -> 1820 (back ~20 IDs) and probe /stats on
     each, recording which return finalized WNBA data. This establishes
     the historical contest_id range we can backfill.
  4. ALSO walk down a wider range with a coarser step to find roughly
     where the WNBA season starts.

Output: /tmp/wnba-probes/leaderboard_*.{json,txt} + a summary printed.
Usage:
    scripts/with-secrets wnba-oracle -- uv run --package wnba-oracle \
      python scripts/probe_leaderboard.py
"""

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

# Candidate leaderboard / entries / rankings endpoint patterns.
# The {cid} placeholder gets replaced with contest id.
LEADERBOARD_CANDIDATES = [
    "/games/playerratingcontest/{cid}/leaderboard",
    "/games/playerratingcontest/{cid}/leaderboard?cohort=top_20",
    "/games/playerratingcontest/{cid}/leaderboard?cohort=0",
    "/games/playerratingcontest/{cid}/leaderboard?limit=20",
    "/games/playerratingcontest/{cid}/leaderboard?limit=20&cohort=0",
    "/games/playerratingcontest/{cid}/rankings",
    "/games/playerratingcontest/{cid}/rankings?cohort=top_20",
    "/games/playerratingcontest/{cid}/entries",
    "/games/playerratingcontest/{cid}/entries?cohort=top_20",
    "/games/playerratingcontest/{cid}/entries?limit=20",
    "/games/playerratingcontest/{cid}/results",
    "/games/playerratingcontest/{cid}/picks",
    "/games/playerratingcontest/{cid}/drafts",
    "/games/playerratingcontest/{cid}/lineups",
    "/games/playerratingcontest/{cid}/standings",
    "/games/playerratingcontest/{cid}/top",
    "/games/playerratingcontest/{cid}/feed",
    "/games/playerratingcontest/{cid}/comments",
    "/games/playerratingcontest/{cid}/players",
    "/games/playerratingcontest/{cid}/winners",
]


async def probe_one(client, base, headers, cid, path_tmpl):
    url = base + path_tmpl.format(cid=cid)
    try:
        r = await client.get(url, headers=headers, timeout=15.0)
    except Exception as exc:
        return {"url": url, "status": "EXC", "exc": str(exc), "body": ""}
    body = r.text[:4096]
    return {"url": url, "status": r.status_code, "body": body}


async def amain():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from wnba_oracle.ingest.realsports import (
        BASE,
        TOKEN_CACHE_PATH,
        _http_headers,
        capture_live_headers,
    )

    device_uuid = os.environ.get("WNBA_DEVICE_UUID") or str(uuid.uuid4())
    device_name = "wnba-oracle-leaderboard-probe-01"
    print(f"device_uuid={device_uuid}", flush=True)

    # Force fresh capture
    if TOKEN_CACHE_PATH.exists():
        TOKEN_CACHE_PATH.unlink()
    print("Capturing fresh auth headers via Playwright (this takes ~15s)...", flush=True)
    headers_obj = await capture_live_headers(device_uuid, device_name)
    h = _http_headers(headers_obj)
    print("  -> captured, real-version=" + headers_obj.real_version, flush=True)

    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        # --- Phase 1: Probe candidate leaderboard endpoints on contest 1840 ---
        cid = 1840
        print(f"\n=== Phase 1: leaderboard endpoint probe on contest {cid} ===", flush=True)
        results = []
        for tmpl in LEADERBOARD_CANDIDATES:
            r = await probe_one(client, BASE, h, cid, tmpl)
            print(f"  {r['status']:>5}  {tmpl}", flush=True)
            results.append(r)
            await asyncio.sleep(0.4)
        (OUT_DIR / "leaderboard_probes.json").write_text(json.dumps(results, indent=2))

        # --- Phase 2: deep dump /stats on contest 1840 (full body) ---
        print(f"\n=== Phase 2: full /stats dump on contest {cid} ===", flush=True)
        url = f"{BASE}/games/playerratingcontest/{cid}/stats"
        r = await client.get(url, headers=h, timeout=20.0)
        (OUT_DIR / f"stats_{cid}.json").write_text(r.text)
        print(f"  /stats status={r.status_code}, bytes={len(r.text)}", flush=True)
        if r.status_code == 200:
            data = r.json()
            print(f"  top-level keys: {sorted(data.keys())}", flush=True)
            contest = data.get("contest", {})
            print(
                f"  contest.sport={contest.get('sport')}, "
                f"contest.day={contest.get('day')}, "
                f"isFinalized={contest.get('isFinalized')}",
                flush=True,
            )

        # --- Phase 3: full /contest meta dump on 1840 (info.rankDisplayInfos) ---
        print(f"\n=== Phase 3: contest meta dump on {cid} ===", flush=True)
        url = f"{BASE}/games/playerratingcontest/{cid}?contestType=sport&source=home"
        r = await client.get(url, headers=h, timeout=20.0)
        (OUT_DIR / f"contest_meta_{cid}.json").write_text(r.text)
        print(f"  status={r.status_code}, bytes={len(r.text)}", flush=True)
        if r.status_code == 200:
            data = r.json()
            info = data.get("info") or {}
            keys_in_info = sorted(info.keys())
            print(f"  info keys: {keys_in_info}", flush=True)
            rdi = info.get("rankDisplayInfos")
            print(f"  rankDisplayInfos present={rdi is not None}, len={len(rdi or [])}", flush=True)

        # --- Phase 4: walk back contest_id 1840 -> 1820, recording sport + day ---
        print("\n=== Phase 4: walk contest ids 1840 down to 1820 ===", flush=True)
        walk_results = []
        for cid in range(1840, 1819, -1):
            url = f"{BASE}/games/playerratingcontest/{cid}/stats"
            try:
                r = await client.get(url, headers=h, timeout=15.0)
            except Exception as exc:
                walk_results.append({"cid": cid, "status": "EXC", "exc": str(exc)})
                continue
            row = {"cid": cid, "status": r.status_code}
            if r.status_code == 200:
                try:
                    data = r.json()
                    contest = data.get("contest") or {}
                    row["sport"] = contest.get("sport")
                    row["day"] = contest.get("day")
                    row["isFinalized"] = contest.get("isFinalized")
                    sections = data.get("draftStats") or []
                    row["n_sections"] = len(sections)
                    row["n_players"] = sum(
                        len(s.get("players") or []) for s in sections
                    )
                except Exception as exc:
                    row["parse_err"] = str(exc)
            print(
                f"  cid={cid}  status={row['status']}  "
                f"sport={row.get('sport','?')}  day={row.get('day','?')}  "
                f"final={row.get('isFinalized','?')}  "
                f"players={row.get('n_players','?')}",
                flush=True,
            )
            walk_results.append(row)
            await asyncio.sleep(0.5)
        (OUT_DIR / "walk_1840_1820.json").write_text(json.dumps(walk_results, indent=2))

        # --- Phase 5: coarse walk back ~200 ids to find season start ---
        print("\n=== Phase 5: coarse walk to find season start ===", flush=True)
        coarse = []
        for cid in range(1840, 1600, -20):
            url = f"{BASE}/games/playerratingcontest/{cid}/stats"
            try:
                r = await client.get(url, headers=h, timeout=15.0)
            except Exception as exc:
                coarse.append({"cid": cid, "status": "EXC", "exc": str(exc)})
                continue
            row = {"cid": cid, "status": r.status_code}
            if r.status_code == 200:
                try:
                    data = r.json()
                    contest = data.get("contest") or {}
                    row["sport"] = contest.get("sport")
                    row["day"] = contest.get("day")
                except Exception:
                    pass
            print(
                f"  cid={cid}  status={row['status']}  "
                f"sport={row.get('sport','?')}  day={row.get('day','?')}",
                flush=True,
            )
            coarse.append(row)
            await asyncio.sleep(0.6)
        (OUT_DIR / "coarse_walk.json").write_text(json.dumps(coarse, indent=2))

    print("\nProbe done. Outputs in /tmp/wnba-probes/")


if __name__ == "__main__":
    asyncio.run(amain())
