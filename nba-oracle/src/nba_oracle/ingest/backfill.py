"""Observation-only NBA Corpus G backfill gate.

Honest first slice: write a blocked coverage matrix and exit non-zero when the
shared Real Sports session is unavailable. No HTTP calls, no credential minting,
no contest entry. Live season-by-season ingest is a later authorized step once
auth is present on the runtime surface.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from oracle_core.artifacts import atomic_write_json

from nba_oracle.calendar.season import NEXT_REGULAR_SEASON_OPEN, tracked_seasons
from nba_oracle.data.coverage_matrix import empty_gap_matrix, matrix_to_dict
from nba_oracle.data.paths import coverage_matrix_path
from nba_oracle.ingest.auth import auth_presence


def _today_et() -> date:
    from datetime import datetime

    return datetime.now(ZoneInfo("America/New_York")).date()


def run(*, dry_run: bool = False, matrix_out: Path | None = None) -> int:
    """Return 0 only when auth is present; otherwise write gaps and return 2."""

    today = _today_et()
    presence = auth_presence()
    rows = empty_gap_matrix(
        now=today,
        blocked_reason=presence.blocked_reason or "realsports_auth_unavailable",
    )
    payload = matrix_to_dict(rows)
    payload["next_regular_season_open"] = NEXT_REGULAR_SEASON_OPEN.isoformat()
    payload["tracked_season_count"] = len(tracked_seasons(today))
    payload["auth"] = {
        "storage_state_env_present": presence.storage_state_env_present,
        "storage_state_file_present": presence.storage_state_file_present,
        "ready": presence.ready,
        "blocked_reason": presence.blocked_reason,
    }

    out = matrix_out or coverage_matrix_path()
    if dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(out, payload)
        print(
            json.dumps(
                {
                    "wrote": str(out),
                    "tracked_season_count": payload["tracked_season_count"],
                    "auth_ready": presence.ready,
                    "blocked_reason": presence.blocked_reason,
                    "next_regular_season_open": payload["next_regular_season_open"],
                },
                sort_keys=True,
            )
        )

    if not presence.ready:
        return 2
    # Auth present: still no live game-id census in this scaffold slice.
    print(
        json.dumps(
            {
                "status": "auth_present_ingest_not_wired",
                "note": (
                    "Shared Real Sports material is present, but NBA Corpus G "
                    "HTTP ingest is not implemented in this PR. Do not claim "
                    "historical rows loaded."
                ),
            },
            sort_keys=True,
        )
    )
    return 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="NBA Corpus G backfill gate (auth-blocked coverage matrix)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matrix JSON to stdout; do not write.",
    )
    parser.add_argument(
        "--matrix-out",
        type=Path,
        default=None,
        help="Override coverage matrix output path.",
    )
    args = parser.parse_args(argv)
    return run(dry_run=args.dry_run, matrix_out=args.matrix_out)


if __name__ == "__main__":
    sys.exit(main())
