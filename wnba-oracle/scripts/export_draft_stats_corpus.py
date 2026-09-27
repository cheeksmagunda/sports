#!/usr/bin/env python3
"""Dump WNBA slate_labels (all sections) + contest_leaderboards into corpus layout.

Writes kind-first paths for the sibling Real Sports corpus (#526)::

  total_value_leaderboards/wnba/{year}/slate_{date}/highestBoostedValuePlayers.json
  recorded_states/wnba/{year}/slate_{date}/draft_stats_all_sections.jsonl
  recorded_states/wnba/{year}/slate_{date}/contest_leaderboards.json
  manifest/draft_stats_sections.json

Default mode is offline demo rows (no database, no secrets). Live export
requires DATABASE_URL in the process environment (Codespace Railway inject)
and never prints connection strings.

Usage::

    uv run --frozen --package wnba-oracle \\
      python wnba-oracle/scripts/export_draft_stats_corpus.py \\
      --corpus-root /tmp/sports-realsports-corpus --demo

    # Live (Codespace with railway-env DATABASE_URL):
    uv run --frozen --package wnba-oracle \\
      python wnba-oracle/scripts/export_draft_stats_corpus.py \\
      --corpus-root /tmp/sports-realsports-corpus --from-database
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from wnba_oracle.corpus.draft_stats_export import (
    export_slates,
    fake_demo_rows,
    write_section_catalog,
)


def _load_from_database() -> tuple[list[dict], list[dict]]:
    """Read slate_labels + contest_leaderboards without printing secrets."""

    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit(
            "DATABASE_URL is required for --from-database "
            "(inject via scripts/codespace-railway-env; never mint secrets)."
        )
    from sqlalchemy import create_engine, text

    from wnba_oracle.common.db_utils import normalize_postgres_url

    engine = create_engine(normalize_postgres_url(url), pool_pre_ping=True)
    label_sql = text(
        "SELECT contest_id, slate_date, section, platform_player_id, display_name, "
        "team_key, card_boost, drafts, real_score, ingested_at "
        "FROM slate_labels ORDER BY slate_date, contest_id, section, platform_player_id"
    )
    board_sql = text(
        "SELECT contest_id, slate_date, entry_id, rank, paged_rank, user_id, score, "
        "lineup, num_brawlers, ingested_at "
        "FROM contest_leaderboards ORDER BY slate_date, contest_id, rank, entry_id"
    )
    with engine.connect() as connection:
        labels = [dict(row._mapping) for row in connection.execute(label_sql)]
        boards = [dict(row._mapping) for row in connection.execute(board_sql)]
    return labels, boards


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-root",
        type=Path,
        required=True,
        help="Local staging root (sibling corpus checkout or /tmp path)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--demo",
        action="store_true",
        help="Write schema-faithful demo rows (offline; no database)",
    )
    mode.add_argument(
        "--from-database",
        action="store_true",
        help="Read Postgres slate_labels + contest_leaderboards via DATABASE_URL",
    )
    mode.add_argument(
        "--catalog-only",
        action="store_true",
        help="Write only manifest/draft_stats_sections.json",
    )
    parser.add_argument(
        "--slate-date",
        action="append",
        default=None,
        help="Optional slate date filter (repeatable). Default: all dates present.",
    )
    args = parser.parse_args(argv)

    root = args.corpus_root
    root.mkdir(parents=True, exist_ok=True)

    if args.catalog_only:
        path = write_section_catalog(root)
        print(json.dumps({"catalog": str(path), "mode": "catalog-only"}))
        return 0

    if args.demo:
        labels, boards = fake_demo_rows()
        mode_name = "demo"
    else:
        labels, boards = _load_from_database()
        mode_name = "database"

    summaries = export_slates(
        root,
        label_rows=labels,
        leaderboard_rows=boards,
        slate_dates=args.slate_date,
    )
    print(
        json.dumps(
            {
                "mode": mode_name,
                "slate_count": len(summaries),
                "label_rows": len(labels),
                "leaderboard_rows": len(boards),
                "sections": sorted(
                    {section for summary in summaries for section in summary.sections}
                ),
                "slates": [
                    {
                        "slate_date": s.slate_date,
                        "hv_rows": s.hv_rows,
                        "recorded_draft_stats_rows": s.recorded_draft_stats_rows,
                        "recorded_lineup_rows": s.recorded_lineup_rows,
                        "sections": list(s.sections),
                        "tv_path": s.tv_path,
                        "recorded_draft_stats_path": s.recorded_draft_stats_path,
                        "recorded_lineups_path": s.recorded_lineups_path,
                    }
                    for s in summaries
                ],
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
