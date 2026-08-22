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

The manual GitHub Action (.github/workflows/corpus-backup.yml) runs this and
commits the output to the orphan `backups` branch, off `main`, so backups never
retrigger Railway deploys.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import sys
import urllib.parse

import pandas as pd
from corpus_backup_common import (
    atomic_write_bytes,
    atomic_write_json,
    build_manifest,
    validate_snapshot,
)
from sqlalchemy import create_engine, text

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
OUT = pathlib.Path(os.environ.get("CORPUS_BACKUP_DIR", "data/backups"))


def _portable_database_url(url: str) -> str:
    """Remove a machine-local TLS root path and use PGSSLROOTCERT instead."""

    parsed = urllib.parse.urlsplit(url)
    query = [
        (name, value)
        for name, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if name.lower() != "sslrootcert"
    ]
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
    )


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8")


def _table_details(frame: pd.DataFrame, table: str) -> dict[str, object]:
    slate_dates = frame["slate_date"].astype(str) if "slate_date" in frame.columns else None
    return {
        "file": f"{table}.csv",
        "columns": [str(column) for column in frame.columns],
        "rows": len(frame),
        "slates": int(slate_dates.nunique()) if slate_dates is not None else None,
        "min_slate": (slate_dates.min() if slate_dates is not None and len(frame) else None),
        "max_slate": (slate_dates.max() if slate_dates is not None and len(frame) else None),
    }


def _assert_no_regression(
    manifest: dict[str, object],
    previous_manifest_path: pathlib.Path | None,
    *,
    allow_regression: bool,
) -> None:
    """Reject a smaller or older corpus unless an operator explicitly allows it."""

    if previous_manifest_path is None or not previous_manifest_path.is_file():
        return
    try:
        previous = json.loads(previous_manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("previous corpus manifest could not be read") from exc
    previous_tables = previous.get("tables") if isinstance(previous, dict) else None
    current_tables = manifest.get("tables")
    if not isinstance(previous_tables, dict) or not isinstance(current_tables, dict):
        raise RuntimeError("previous corpus manifest has an invalid shape")

    regressions: list[str] = []
    for table in sorted(CORPUS_QUERIES):
        previous_entry = previous_tables.get(table)
        current_entry = current_tables.get(table)
        if not isinstance(previous_entry, dict) or not isinstance(current_entry, dict):
            raise RuntimeError(f"previous corpus manifest is missing {table}")
        previous_rows = previous_entry.get("rows")
        current_rows = current_entry.get("rows")
        if not isinstance(previous_rows, int) or not isinstance(current_rows, int):
            raise RuntimeError(f"corpus manifest row count for {table} is invalid")
        if current_rows < previous_rows:
            regressions.append(f"{table} row count decreased")
        previous_max = previous_entry.get("max_slate")
        current_max = current_entry.get("max_slate")
        if isinstance(previous_max, str) and (
            not isinstance(current_max, str) or current_max < previous_max
        ):
            regressions.append(f"{table} maximum slate moved backward")
    if regressions and not allow_regression:
        raise RuntimeError("corpus backup regression: " + "; ".join(regressions))


def export_corpus(engine, output_dir: pathlib.Path) -> dict[str, object]:
    """Export all corpus tables from one read-only repeatable-read snapshot."""

    output_dir.mkdir(parents=True, exist_ok=True)
    details: dict[str, dict[str, object]] = {}
    connection = engine.connect().execution_options(isolation_level="REPEATABLE READ")
    try:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            for table, query in CORPUS_QUERIES.items():
                frame = pd.read_sql(text(query), connection)
                if frame.empty:
                    raise RuntimeError(f"refusing to publish an empty {table} backup")
                path = output_dir / f"{table}.csv"
                atomic_write_bytes(path, _csv_bytes(frame))
                details[table] = _table_details(frame, table)
                print(f"backed up {table}: {len(frame)} rows -> {path}")
    finally:
        connection.close()

    manifest = build_manifest(
        output_dir,
        details,
        generated_at=datetime.datetime.now(datetime.UTC),
    )
    previous_setting = os.environ.get("CORPUS_PREVIOUS_MANIFEST", "").strip()
    _assert_no_regression(
        manifest,
        pathlib.Path(previous_setting) if previous_setting else None,
        allow_regression=os.environ.get("CORPUS_BACKUP_ALLOW_REGRESSION", "").lower() == "true",
    )
    atomic_write_json(output_dir / "manifest.json", manifest)
    validate_snapshot(output_dir, expected_tables=set(CORPUS_QUERIES))
    return manifest


def main() -> int:
    url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: set DATABASE_PUBLIC_URL or DATABASE_URL", file=sys.stderr)
        return 1
    engine = create_engine(
        _portable_database_url(url).replace("postgresql://", "postgresql+psycopg://", 1),
        connect_args={"options": "-c default_transaction_read_only=on"},
    )
    try:
        manifest = export_corpus(engine, OUT)
    except Exception as exc:
        print(f"ERROR: corpus backup failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    print("manifest tables:", ", ".join(sorted(manifest["tables"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
