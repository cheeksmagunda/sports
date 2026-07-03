"""Off-platform logical backup of the irreplaceable WNBA corpus.

Exports the scraped corpus tables (slate_labels + contest_leaderboards) from
Postgres to `data/backups/*.csv` + a manifest. These are the only tables that
cannot be regenerated: once a Real Sports contest ages out, its labels and
finisher lineups are gone. job1_enrichment / frozen_lineups are reproduced by
the daily crons, so they are intentionally NOT backed up here.

Pure-python (no pg_dump binary), so it runs identically on a laptop and in CI.
Reads the connection from DATABASE_PUBLIC_URL (read-only, sslmode=verify-ca)
or, as a fallback, DATABASE_URL. TLS root cert is taken from the URL's
sslrootcert param or the PGSSLROOTCERT env var (libpq).

The nightly GitHub Action (.github/workflows/backup-corpus.yml) runs this and
commits the output to the orphan `backups` branch, off `main`, so backups never
retrigger Railway deploys.
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import sys

import pandas as pd
from sqlalchemy import create_engine

# Only the irreplaceable scraped corpus. lineup is jsonb -> cast to text so the
# CSV round-trips cleanly.
CORPUS_QUERIES = {
    "slate_labels": (
        "select contest_id, slate_date, section, platform_player_id, display_name, "
        "team_key, card_boost, drafts, real_score, ingested_at "
        "from slate_labels order by slate_date, contest_id, platform_player_id"
    ),
    "contest_leaderboards": (
        "select contest_id, slate_date, entry_id, rank, paged_rank, user_id, score, "
        "lineup::text as lineup, num_brawlers, ingested_at "
        "from contest_leaderboards order by slate_date, contest_id, rank"
    ),
}
OUT = pathlib.Path("data/backups")


def main() -> int:
    url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: set DATABASE_PUBLIC_URL or DATABASE_URL", file=sys.stderr)
        return 1
    engine = create_engine(url.replace("postgresql://", "postgresql+psycopg://"))
    OUT.mkdir(parents=True, exist_ok=True)

    manifest: dict = {
        "generated_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "tables": {},
    }
    for table, query in CORPUS_QUERIES.items():
        df = pd.read_sql(query, engine)
        df.to_csv(OUT / f"{table}.csv", index=False)
        sd = df["slate_date"].astype(str) if "slate_date" in df.columns else None
        manifest["tables"][table] = {
            "rows": len(df),
            "slates": int(sd.nunique()) if sd is not None else None,
            "min_slate": (sd.min() if sd is not None and len(df) else None),
            "max_slate": (sd.max() if sd is not None and len(df) else None),
        }
        print(f"backed up {table}: {len(df)} rows -> {OUT / (table + '.csv')}")

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print("manifest:", json.dumps(manifest["tables"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
