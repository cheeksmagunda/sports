"""One-time login flow. Persists scraper/storage_state.json with the
long-lived JWT in localStorage. Run on a developer machine, then base64+gzip
the resulting file into the Railway env var REALSPORTS_STORAGE_STATE_B64GZ.

KNOWN BROKEN headless since ~2026-06-27: realsports.io bot detection
returns 403 ("Please refresh the page and try again") on POST /login from
scripted Chromium, regardless of UA spoofing, webdriver masking, or the
real Chrome channel. The reliable recovery is the Playwright MCP browser
flow documented in AGENTS.md, section "Real Sports". This script is kept
for --headed debugging and for the day the bot check changes.

Usage:
    uv run python scripts/realsports_login.py [--headed]
    (credentials come from REAL_SPORTS_USERNAME / REAL_SPORTS_PASSWORD in
    the session env; Claude Code exports them from .claude/settings.local.json)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from wnba_oracle.ingest.realsports import STORAGE_STATE_PATH, login_and_seed_storage


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--headed", action="store_true", help="show the browser (debug only)"
    )
    args = parser.parse_args()

    login = os.environ.get("REAL_SPORTS_USERNAME", "").strip()
    password = os.environ.get("REAL_SPORTS_PASSWORD", "").strip()
    if not login or not password:
        print(
            "REAL_SPORTS_USERNAME / REAL_SPORTS_PASSWORD must be set in env",
            file=sys.stderr,
        )
        return 2

    asyncio.run(login_and_seed_storage(login, password, headed=args.headed))
    print(f"OK - wrote {STORAGE_STATE_PATH}")
    print("Encode for Railway: gzip -c scraper/storage_state.json | base64")
    return 0


if __name__ == "__main__":
    sys.exit(main())
