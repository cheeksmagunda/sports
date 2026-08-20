"""Materialize a frozen local corpus snapshot for offline model work.

Everything the offline harness reads comes from this snapshot, never from
production. That buys three things: experiments are reproducible (the corpus
does not move under you between runs), they are fast (no network per query),
and they cannot touch prod.

The connection is opened with ``default_transaction_read_only=on``, so Postgres
itself rejects any INSERT/UPDATE/DELETE. That is a server-side guarantee, not a
convention -- which matters, because the ordinary way to run job1 locally
against ``DATABASE_URL`` writes straight to the live tables.

``scripts/backup_corpus.py`` is a different thing and is not a substitute: it
exports only ``slate_labels`` + ``contest_leaderboards`` as the off-site backup.
The harness additionally needs ``job1_enrichment`` (its ``features_json`` is
exactly what prod served that night, so replays are faithful), ``frozen_lineups``
(what we actually committed, in slot order), ``slate_meta`` and
``wnba_game_logs``.

JSONB columns are stored as JSON text so the parquet schema stays flat and
stable; ``scripts/lab.py`` parses them on load.

Usage:
    export DATABASE_URL=...        # prod URL is fine; the session is read-only
    uv run --extra dev python scripts/snapshot_corpus.py
    uv run --extra dev python scripts/snapshot_corpus.py --out data/snapshot
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

import pandas as pd
import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wnba_oracle.common.db_utils import (
    normalize_postgres_url,
    repair_local_sslrootcert,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "data" / "snapshot"

# JSONB columns are cast to text in SQL so pandas gets str, not dict.
TABLES: dict[str, str] = {
    "job1_enrichment": (
        "select id, slate_date, player_id, real_sports_player_id, name, team, opponent, "
        "position, card_boost, features_json::text as features_json, captured_at "
        "from job1_enrichment"
    ),
    "slate_labels": (
        "select id, contest_id, slate_date, section, platform_player_id, display_name, "
        "team_key, card_boost, drafts, real_score, ingested_at from slate_labels"
    ),
    "contest_leaderboards": (
        "select id, contest_id, slate_date, entry_id, rank, paged_rank, user_id, score, "
        "lineup::text as lineup, num_brawlers, ingested_at from contest_leaderboards"
    ),
    "frozen_lineups": (
        "select id, slate_date, model_sha, payout_regime, frozen_at, lineup::text as lineup, "
        "entry_recommendation, expected_payout, metadata_json::text as metadata_json, "
        "freeze_seq, frozen_via from frozen_lineups"
    ),
    "slate_meta": (
        "select slate_date, first_tip_utc, contest_lock_utc, source, updated_at from slate_meta"
    ),
    "wnba_game_logs": "select * from wnba_game_logs",
}

# Per-slate serving-condition tags. A backtest pooled across a regime break
# mixes two different serving conditions and the comparison is meaningless.
# recent_minutes / per_min_rate vanished from enrichment on 2026-08-04 (the
# stats.wnba.com fetch fails soft from Railway's egress) and flapped in July.
REGIME_Q = """
select slate_date::text as slate_date,
       count(*) as n_pool,
       count(*) filter (where features_json ? 'recent_minutes') as n_recent_minutes,
       count(*) filter (where features_json ? 'per_min_rate')   as n_per_min_rate,
       count(*) filter (where features_json ? 'head_features')  as n_head_features,
       count(*) filter (where features_json ? 'prop_points_line') as n_props
from job1_enrichment group by 1 order by 1
"""


def _engine(url: str) -> sa.Engine:
    return sa.create_engine(
        normalize_postgres_url(repair_local_sslrootcert(url, REPO_ROOT)),
        connect_args={"options": "-c default_transaction_read_only=on"},
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="snapshot directory")
    args = ap.parse_args()

    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("[fatal] DATABASE_URL not set", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    eng = _engine(url)

    # Prove the guard is armed before pulling anything, so a misconfigured
    # connection fails here rather than silently allowing a later write.
    with eng.connect() as conn:
        ro = conn.execute(sa.text("show transaction_read_only")).scalar()
        if str(ro).lower() != "on":
            print(f"[fatal] read-only guard not armed (transaction_read_only={ro})", file=sys.stderr)
            return 2

    manifest: dict[str, object] = {
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
        "tables": {},
    }
    with eng.connect() as conn:
        for table, query in TABLES.items():
            df = pd.read_sql(sa.text(query), conn)
            path = out / f"{table}.parquet"
            df.to_parquet(path, index=False)
            manifest["tables"][table] = {"rows": len(df), "file": path.name}  # type: ignore[index]
            print(f"  {table:24s} {len(df):7d} rows -> {path.name}")

        regime = pd.read_sql(sa.text(REGIME_Q), conn)

    regime["minutes_features_present"] = regime["n_recent_minutes"] > 0
    regime.to_parquet(out / "slate_regime.parquet", index=False)
    n_with = int(regime["minutes_features_present"].sum())
    manifest["slate_regime"] = {
        "slates": len(regime),
        "with_minutes_features": n_with,
        "without_minutes_features": int(len(regime) - n_with),
        "file": "slate_regime.parquet",
    }
    print(f"  {'slate_regime':24s} {len(regime):7d} slates -> slate_regime.parquet")
    print(
        f"    minutes features present on {n_with}/{len(regime)} slates; "
        "segment or tag by this before pooling"
    )

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nsnapshot written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
