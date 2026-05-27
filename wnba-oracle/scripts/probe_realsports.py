"""Step 2 probe: confirm WNBA Real Sports endpoints + archive payout curve.

Hits:
  - /home/wnba/next       enumerates today's WNBA games
  - /players/sport/wnba/search?query=a&searchType=ratingLineup  pool sample
  - /home/wnba/day/next   daily contest meta (payout curve)

Saves the responses as fixtures under tests/fixtures/realsports/ and archives
the payout table under data/contest_payouts/. Skips gracefully on no-games
days (off-season). Designed to be re-runnable.

Usage:
    set -a && source .env && set +a
    uv run python scripts/probe_realsports.py [--date YYYY-MM-DD] [--device-uuid UUID]
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import sys
import uuid
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "realsports"
PAYOUTS_DIR = REPO_ROOT / "data" / "contest_payouts"


async def _amain(args: argparse.Namespace) -> int:
    # Late imports so the script doesn't fail on import without playwright.
    from wnba_oracle.ingest.realsports import (
        BASE,
        SPORT,
        StorageStateMissing,
        StorageStateStale,
        _http_headers,
        _real_sports_get_with_retry,
        _search_with_query,
        discover_wnba_contest_id,
        fetch_contest_meta,
        headers_or_capture,
    )

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    PAYOUTS_DIR.mkdir(parents=True, exist_ok=True)

    slate_date = args.date or dt.date.today().isoformat()
    device_uuid = args.device_uuid or os.environ.get("WNBA_DEVICE_UUID") or str(uuid.uuid4())
    device_name = args.device_name or "wnba-oracle-probe-01"

    print(f"slate_date={slate_date}")
    print(f"device_uuid={device_uuid}")

    try:
        headers = await headers_or_capture(device_uuid, device_name)
    except StorageStateMissing as exc:
        print(f"[BLOCK] {exc}", file=sys.stderr)
        print(
            "Run `uv run python scripts/realsports_login.py` first, then re-run the probe.",
            file=sys.stderr,
        )
        return 78
    except StorageStateStale as exc:
        print(f"[BLOCK] {exc}", file=sys.stderr)
        return 78

    h = _http_headers(headers)
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        # 1) /home/wnba/next
        print(f"GET {BASE}/home/{SPORT}/next?cohort=0")
        try:
            r = await _real_sports_get_with_retry(
                client, f"{BASE}/home/{SPORT}/next", headers=h, params={"cohort": 0}
            )
            home_data = r.json()
        except Exception as exc:
            print(f"[ERR] /home/{SPORT}/next failed: {exc}", file=sys.stderr)
            return 1
        out = FIXTURES_DIR / f"home_next_{slate_date}.json"
        out.write_text(json.dumps(home_data, indent=2))
        games = (home_data.get("latestDayContent") or {}).get("games") or []
        print(f"  -> {len(games)} games, fixture: {out.relative_to(REPO_ROOT)}")

        # 2) /players/sport/wnba/search?query=a (single prefix to keep the probe cheap)
        print(f"GET {BASE}/players/sport/{SPORT}/search?query=a&searchType=ratingLineup")
        try:
            _status, players = await _search_with_query(slate_date, "a", h, client)
        except Exception as exc:
            print(f"[ERR] /players/sport/{SPORT}/search failed: {exc}", file=sys.stderr)
            return 1
        out = FIXTURES_DIR / f"search_a_{slate_date}.json"
        out.write_text(json.dumps({"players": players}, indent=2))
        print(f"  -> {len(players)} players, fixture: {out.relative_to(REPO_ROOT)}")

        # 3) Discover WNBA contest id via Playwright SPA sniff, then fetch
        #    contest metadata. Payout structure (`info.rankDisplayInfos`) is
        #    null pregame; archive whatever shape we capture so the picker's
        #    payout loader can ingest it once it populates post-tip.
        print("Discovering active WNBA contest id (Playwright sniff)...")
        try:
            contest_id = await discover_wnba_contest_id()
        except StorageStateMissing as exc:
            print(f"[ERR] {exc}", file=sys.stderr)
            return 1
        if contest_id is None:
            print("  -> no contest id observed; skipping contest meta probe")
        else:
            print(f"  -> candidate contest id: {contest_id}")
            try:
                meta = await fetch_contest_meta(contest_id, headers, client)
            except Exception as exc:
                print(f"[ERR] contest meta fetch failed: {exc}", file=sys.stderr)
                return 1
            contest_sport = meta.get("info", {}).get("contest", {}).get("sport")
            if contest_sport != SPORT:
                print(
                    f"  -> contest {contest_id} sport={contest_sport}; "
                    "discover_wnba_contest_id likely returned the MLB contest. "
                    "Re-run with active WNBA tab.",
                    file=sys.stderr,
                )
            out = FIXTURES_DIR / f"contest_{contest_id}_{slate_date}.json"
            out.write_text(json.dumps(meta, indent=2))
            archive = PAYOUTS_DIR / f"contest_{contest_id}_{slate_date}.json"
            archive.write_text(json.dumps(meta, indent=2))
            print(
                f"  -> fixture: {out.relative_to(REPO_ROOT)}, "
                f"archive: {archive.relative_to(REPO_ROOT)}"
            )
            rdi = meta.get("info", {}).get("rankDisplayInfos") or []
            if not rdi:
                print(
                    "  note: rankDisplayInfos empty (contest pregame); payout "
                    "structure becomes available post-tip. Picker defaults to "
                    "top_20 payout regime per Part 1.2."
                )

    print("\nprobe OK.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Real Sports WNBA endpoints")
    parser.add_argument("--date", help="slate date YYYY-MM-DD (default: today)")
    parser.add_argument("--device-uuid", help="override device UUID")
    parser.add_argument("--device-name", help="override device name")
    args = parser.parse_args()
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
