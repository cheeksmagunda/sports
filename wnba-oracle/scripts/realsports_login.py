"""One-time login flow. Persists scraper/storage_state.json with the
long-lived JWT in localStorage. Run on a developer machine, then base64+gzip
the resulting file into the Railway env var REALSPORTS_STORAGE_STATE_B64GZ.

Usage:
    set -a && source .env && set +a
    uv run python scripts/realsports_login.py [--headed]
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
