"""End-to-end manual fire against the live Real Sports slate.

Steps:
1. Job 1 (live data): pool + odds + lineups -> persisted enrichment.
2. Job 2 (live data): picker -> frozen lineup.
3. Watchdog: post-Job-2 trigger evaluation.

Fixture mode (--fixtures) replays from tests/fixtures/realsports/ instead
of hitting the live platform; useful off-season / no-games days.

Usage:
    set -a && source .env && set +a
    uv run python scripts/manual_fire.py
    uv run python scripts/manual_fire.py --fixtures
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from wnba_oracle.common.logging import configure_logging, get_logger

REPO_ROOT = Path(__file__).resolve().parents[1]

log = get_logger("oracle.manual_fire")


def _ensure_db_available() -> bool:
    from wnba_oracle.common.settings import get_settings

    s = get_settings()
    if not s.database_url:
        print(
            "[skip] DATABASE_URL not set; manual_fire does not persist when DB is offline.",
            file=sys.stderr,
        )
        return False
    return True


def _run_live_fire(slate_date: str) -> int:
    from wnba_oracle.scheduler.job1 import run as run_job1
    from wnba_oracle.scheduler.job2 import run as run_job2
    from wnba_oracle.scheduler.watchdog import run_watchdog

    j1 = run_job1(slate_date)
    print(json.dumps({"job1": j1.__dict__}, indent=2, default=str))
    j2 = run_job2(slate_date)
    print(
        json.dumps(
            {
                "job2": {
                    "slate_date": j2.slate_date,
                    "model_sha": j2.model_sha,
                    "frozen": j2.frozen,
                    "reason": j2.reason,
                    "recommendation_player_ids": list(j2.recommendation.player_ids)
                    if j2.recommendation
                    else None,
                    "expected_payout": j2.recommendation.expected_payout
                    if j2.recommendation
                    else None,
                    "entry_flag": j2.recommendation.entry_flag if j2.recommendation else None,
                }
            },
            indent=2,
            default=str,
        )
    )
    events = run_watchdog(slate_date)
    print(json.dumps({"watchdog": {"events": len(events)}}, indent=2))
    return 0


def _run_fixture_fire(slate_date: str) -> int:
    """Hits no network; reads tests/fixtures/realsports/ + assumes Postgres
    is reachable for the freeze step. Useful off-season or no-game days."""
    import json as _json

    from wnba_oracle.ingest.realsports import _parse_pool

    pool_path = REPO_ROOT / "tests" / "fixtures" / "realsports" / f"search_a_{slate_date}.json"
    if not pool_path.exists():
        # Fall back to any search fixture
        candidates = sorted(
            (REPO_ROOT / "tests" / "fixtures" / "realsports").glob("search_*_*.json")
        )
        if not candidates:
            log.error("no fixture pool available; run scripts/probe_realsports.py first")
            return 2
        pool_path = candidates[-1]
    body = _json.loads(pool_path.read_text())
    players = body.get("players", [])
    # Coerce types for the parser
    for p in players:
        if p.get("multiplierBonus") is None:
            p["multiplierBonus"] = 0.0
        team = p.get("team")
        if isinstance(team, dict) and not team.get("key"):
            team["key"] = "UNK"
    pool = _parse_pool({"players": players})
    print(f"[fixture] loaded {len(pool)} players from {pool_path.name}")
    if len(pool) < 5:
        print("[fixture] pool too small for picker", file=sys.stderr)
        return 0
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", action="store_true", help="replay from fixtures")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    args = parser.parse_args()
    configure_logging("INFO")

    if args.fixtures:
        return _run_fixture_fire(args.date)
    if not _ensure_db_available():
        return 1
    return _run_live_fire(args.date)


if __name__ == "__main__":
    sys.exit(main())
