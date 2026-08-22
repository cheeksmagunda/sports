"""One-off backfill: merge the D69 `head_features` row into existing
job1_enrichment rows for a given slate_date.

Use when cron-job1 fired with pre-D69 code (no head_features persisted) and we
need TONIGHT's freeze to serve from the trained heads anyway. Reads
wnba_game_logs from the canonical Postgres store via DATABASE_PUBLIC_URL,
builds the head feature row per player with the SAME function job1 now uses,
matches by (initial, last, team), and UPSERTs the merged features_json back.

Idempotent. Re-running on the same slate overwrites. Pure addition: rows
without a head match get features_json untouched.

Usage:
    scripts/with-secrets wnba-oracle -- uv run --package wnba-oracle \
      python scripts/backfill_head_features.py --slate-date 2026-06-06
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

import polars as pl
import sqlalchemy as sa
from sqlalchemy import text

from wnba_oracle.features.serving_features import (
    build_head_feature_lookup,
)
from wnba_oracle.features.serving_features import (
    lookup as head_feature_lookup,
)

SELECT_ENRICHMENT = text(
    "SELECT player_id, real_sports_player_id, name, team, features_json "
    "FROM job1_enrichment WHERE slate_date = :sd"
)

UPDATE_FEATURES = text(
    "UPDATE job1_enrichment SET features_json = CAST(:features AS JSONB) "
    "WHERE slate_date = :sd AND player_id = :pid"
)

SELECT_GAME_LOGS = text(
    "SELECT game_date, player_id, player_name, first_initial, last_name, "
    "team, opponent, home_away, game_id, min, season, "
    "pts, reb, oreb, dreb, ast, stl, blk, tov, "
    "fgm, fga, fg3m, ftm, fta "
    "FROM wnba_game_logs ORDER BY game_date, player_id"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slate-date", default=dt.date.today().isoformat(), help="ISO date")
    parser.add_argument("--dry-run", action="store_true", help="Print plan, do not write")
    args = parser.parse_args()
    sd = args.slate_date

    db_url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_PUBLIC_URL or DATABASE_URL must be set", file=sys.stderr)
        return 1
    # Project uses psycopg v3 (per pyproject); coerce both schemes to the
    # postgresql+psycopg:// driver SQLAlchemy needs.
    if db_url.startswith("postgres://"):
        db_url = "postgresql+psycopg://" + db_url[len("postgres://") :]
    elif db_url.startswith("postgresql://"):
        db_url = "postgresql+psycopg://" + db_url[len("postgresql://") :]

    eng = sa.create_engine(db_url)

    # 1) Read wnba_game_logs from Postgres.
    with eng.connect() as conn:
        rows = conn.execute(SELECT_GAME_LOGS).fetchall()
    if not rows:
        print("ERROR: wnba_game_logs is empty", file=sys.stderr)
        return 2
    gl = pl.from_dicts([dict(r._mapping) for r in rows])
    print(f"game_logs rows={len(gl)}, latest={gl.get_column('game_date').max()}")

    # 2) Build the head feature lookup AS-OF the slate date.
    feats = build_head_feature_lookup(gl, slate_date=sd)
    print(f"head feature lookup keys={len(feats)}")

    # 3) Walk today's enrichment rows; merge head_features into each.
    with eng.connect() as conn:
        enrich_rows = conn.execute(SELECT_ENRICHMENT, {"sd": sd}).fetchall()
    if not enrich_rows:
        print(f"ERROR: no job1_enrichment rows for slate_date={sd}", file=sys.stderr)
        return 3
    print(f"job1_enrichment rows for {sd}: {len(enrich_rows)}")

    n_matched = 0
    n_skipped = 0
    updates: list[dict] = []
    for r in enrich_rows:
        row = dict(r._mapping)
        name = str(row.get("name", "") or "")
        team = str(row.get("team", "") or "")
        hf = head_feature_lookup(feats, display_name=name, team=team)
        if hf is None:
            n_skipped += 1
            continue
        fj = row.get("features_json") or {}
        if isinstance(fj, str):
            try:
                fj = json.loads(fj)
            except json.JSONDecodeError:
                fj = {}
        if not isinstance(fj, dict):
            fj = {}
        # Pure merge: head_features is a brand-new key, no other field changes.
        fj["head_features"] = hf
        updates.append({"sd": sd, "pid": int(row["player_id"]), "features": json.dumps(fj)})
        n_matched += 1

    print(f"matched: {n_matched}, skipped (no game-log history): {n_skipped}")

    if args.dry_run:
        print("DRY RUN: no writes")
        return 0

    # 4) Apply updates.
    with eng.begin() as conn:
        for u in updates:
            conn.execute(UPDATE_FEATURES, u)
    print(f"updated {len(updates)} rows in job1_enrichment for {sd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
