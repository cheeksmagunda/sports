"""Backfill WNBA per-game minutes + box lines from stats.wnba.com (nba_api).

This is the data foundation for the minutes/role model (D54): the corpus has
realized real_score + card_boost but NO minutes, and minutes is the one signal
orthogonal to the boost. One PlayerGameLogs call per season returns the entire
league's per-game box scores with precise MIN, dated, with team abbreviations
that match the corpus team_key.

The fetch/parse/upsert now lives in src/wnba_oracle/ingest/minutes_backfill.py so
the nightly dayclose cron shares it (D102); this script reloads all seasons.

Run: uv run python scripts/backfill_minutes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wnba_oracle.ingest.minutes_backfill import refresh_game_logs

SEASONS = ["2024", "2025", "2026"]


def main() -> None:
    n = refresh_game_logs(SEASONS)
    if n == 0:
        raise SystemExit("no game logs fetched")
    print(f"upserted {n} rows to Postgres wnba_game_logs across seasons {SEASONS}")


if __name__ == "__main__":
    main()
