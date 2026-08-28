"""Export validated (slate_date, team, opponent) identity from job1_enrichment.

job1_enrichment is captured from the same Real Sports platform pool that
produces slate_labels.team_key (one row per (slate_date, player_id), never
pruned), so `team` here is directly comparable to team_key with no
cross-provider identity map needed -- unlike wnba_game_logs, which is
nba_api-sourced with its own team vocabulary (see wnba-oracle/AGENTS.md: do
not join the gamelog and label corpora without an explicit identity map).

Used by .github/workflows/model-research-benchmark.yml's prefetch job to
give the DB-free sharded benchmark matrix real game identity, so
scripts/build_model_research_benchmark.py never has to fabricate an
opponent (see that script and wnba_oracle.db.reads.read_game_identity).

This is a plain export, not part of the irreplaceable-corpus backup pipeline
(backup_corpus.py): job1_enrichment is reproducible from the daily crons,
and this table is small and research-only, so it deliberately stays out of
the validated-manifest backups branch.

Pure-python (no pg_dump binary), reusing backup_corpus.py's connection
conventions. Reads the connection from DATABASE_PUBLIC_URL (read-only,
sslmode=verify-ca) or, as a fallback, DATABASE_URL. TLS root cert is taken
from the URL's sslrootcert param or the PGSSLROOTCERT env var (libpq).
"""

from __future__ import annotations

import os
import pathlib
import sys

import pandas as pd
from corpus_backup_common import atomic_write_bytes, portable_database_url, require_verified_tls
from sqlalchemy import create_engine, text

QUERY = (
    "select distinct slate_date, team, opponent from job1_enrichment "
    "where opponent is not null and opponent != '' "
    "order by slate_date, team"
)
OUT = pathlib.Path(os.environ.get("GAME_IDENTITY_OUTPUT_DIR", "."))


def export_game_identity(engine, output_dir: pathlib.Path) -> int:
    """Export the identity table from one read-only repeatable-read snapshot."""

    output_dir.mkdir(parents=True, exist_ok=True)
    connection = engine.connect().execution_options(isolation_level="REPEATABLE READ")
    try:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            frame = pd.read_sql(text(QUERY), connection)
    finally:
        connection.close()
    path = output_dir / "game_identity.csv"
    atomic_write_bytes(path, frame.to_csv(index=False).encode("utf-8"))
    print(f"exported game identity: {len(frame)} rows -> {path}")
    return len(frame)


def main() -> int:
    url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: set DATABASE_PUBLIC_URL or DATABASE_URL", file=sys.stderr)
        return 1
    try:
        require_verified_tls(url)
    except RuntimeError as exc:
        print(f"ERROR: game identity export configuration rejected: {exc}", file=sys.stderr)
        return 1
    engine = create_engine(
        portable_database_url(url).replace("postgresql://", "postgresql+psycopg://", 1),
        connect_args={"options": "-c default_transaction_read_only=on"},
    )
    try:
        rows = export_game_identity(engine, OUT)
    except Exception as exc:
        print(f"ERROR: game identity export failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    if rows == 0:
        print("ERROR: game identity export returned zero rows", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
