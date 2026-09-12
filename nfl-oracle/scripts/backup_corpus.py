"""Off-platform logical backup of the irreplaceable NFL decision corpus.

Exports frozen lineups (what we picked), prepared decisions (the input
context bundle and output recommendation at decision time), dayclose grades
(accuracy vs. real-world actuals), and player_results (every player's draft
stats across the whole field, for every finalized contest we graded, not
just our five picks) to `data/backups/*.csv` + a manifest. model_bundle /
active_model artifacts are reproducible from Corpus G and are intentionally
NOT backed up here, mirroring wnba-oracle/scripts/backup_corpus.py's "only
the irreplaceable" scope.

Built on the existing, tested RecommendationStore.export_backup() rather than
raw SQL, so this reuses the same digest-chain verification `nfl-pipeline
backup-export` already relies on. Pure-python (stdlib csv, no pandas), so it
runs identically on a laptop and in CI.

Reads the connection from NFL_BACKUP_DATABASE_URL (read-only, sslmode=
verify-ca or verify-full) or, as a fallback, NFL_DATABASE_URL. TLS root cert
is taken from PGSSLROOTCERT (libpq).

The GitHub Action (.github/workflows/nfl-corpus-backup.yml) runs this and
commits the output to the shared orphan `backups` branch, off `main`, under
nfl-oracle/data/backups/, so backups never retrigger a deploy.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import sys
from typing import Any

from nfl_corpus_backup_common import (
    TABLE_COLUMNS,
    assert_no_regression,
    atomic_write_bytes,
    atomic_write_json,
    build_manifest,
    portable_postgres_url,
    require_verified_tls,
    rows_to_csv_bytes,
    validate_snapshot,
)
from sqlalchemy import create_engine

from nfl_oracle.recommendations.dayclose import DAYCLOSE_GRADE_KIND_PREFIX
from nfl_oracle.recommendations.store import RecommendationStore

PREPARED_KIND_PREFIX = "prepared"
OUT = pathlib.Path(os.environ.get("CORPUS_BACKUP_DIR", "data/backups"))


def _frozen_lineup_rows(freezes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "slate_date": record.get("slate_date"),
            "contest_id": record.get("contest_id"),
            "sequence": record.get("sequence"),
            "digest": record.get("digest"),
            "previous_digest": record.get("previous_digest"),
            "frozen_at": record.get("frozen_at"),
            "decision_at": record.get("decision_at"),
            "model_fingerprint": record.get("model_fingerprint"),
            "input_fingerprint": record.get("input_fingerprint"),
            "lineup_json": json.dumps(record.get("lineup"), sort_keys=True, separators=(",", ":")),
            "slate_json": json.dumps(record.get("slate"), sort_keys=True, separators=(",", ":")),
        }
        for record in freezes
    ]


def _artifact_rows(artifacts: list[dict[str, Any]], *, kind_prefix: str) -> list[dict[str, Any]]:
    prefix = f"{kind_prefix}:"
    rows = []
    for artifact in artifacts:
        kind = artifact.get("kind")
        if not isinstance(kind, str) or not kind.startswith(prefix):
            continue
        rows.append(
            {
                "day": kind[len(prefix) :],
                "sha256": artifact.get("sha256"),
                "created_at": artifact.get("created_at"),
                "payload_json": json.dumps(
                    artifact.get("payload"), sort_keys=True, separators=(",", ":")
                ),
            }
        )
    rows.sort(key=lambda row: str(row["day"]))
    return rows


def _player_result_rows(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per player per finalized contest, across the whole field.

    Sourced from dayclose_grades artifacts' embedded
    slate_results.player_draft_stats (nfl_oracle.contests.schema.DraftStatRow,
    already parsed and law-verified by contests.parse.load_contest at grade
    time) - no separate query or Postgres schema change needed.
    """

    prefix = f"{DAYCLOSE_GRADE_KIND_PREFIX}:"
    rows: list[dict[str, Any]] = []
    for artifact in artifacts:
        kind = artifact.get("kind")
        if not isinstance(kind, str) or not kind.startswith(prefix):
            continue
        payload = artifact.get("payload")
        if not isinstance(payload, dict):
            continue
        slate_results = payload.get("slate_results")
        if not isinstance(slate_results, dict):
            continue
        day = kind[len(prefix) :]
        contest_id = payload.get("contest_id")
        for stat in slate_results.get("player_draft_stats") or []:
            if not isinstance(stat, dict):
                continue
            rows.append(
                {
                    "day": day,
                    "contest_id": contest_id,
                    "player_id": stat.get("player_id"),
                    "display_name": stat.get("display_name"),
                    "team_id": stat.get("team_id"),
                    "section": stat.get("section"),
                    "value": stat.get("value"),
                    "draft_count": stat.get("draft_count"),
                    "card_boost": stat.get("card_boost"),
                    "avg_effective_multiplier": stat.get("avg_effective_multiplier"),
                    "avg_score": stat.get("avg_score"),
                    "highest_score": stat.get("highest_score"),
                }
            )
    rows.sort(key=lambda row: (str(row["day"]), row["player_id"] or 0))
    return rows


def export_corpus(engine: Any, output_dir: pathlib.Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    backup = RecommendationStore(engine).export_backup()

    tables = {
        "frozen_lineups": _frozen_lineup_rows(backup["freezes"]),
        "prepared_decisions": _artifact_rows(backup["artifacts"], kind_prefix=PREPARED_KIND_PREFIX),
        "dayclose_grades": _artifact_rows(
            backup["artifacts"], kind_prefix=DAYCLOSE_GRADE_KIND_PREFIX
        ),
        "player_results": _player_result_rows(backup["artifacts"]),
    }
    row_counts: dict[str, int] = {}
    for table, rows in tables.items():
        columns = TABLE_COLUMNS[table]
        path = output_dir / f"{table}.csv"
        atomic_write_bytes(path, rows_to_csv_bytes(rows, columns))
        row_counts[table] = len(rows)
        print(f"backed up {table}: {len(rows)} rows -> {path}")

    manifest = build_manifest(
        output_dir, row_counts, generated_at=datetime.datetime.now(datetime.UTC)
    )
    previous_setting = os.environ.get("CORPUS_PREVIOUS_MANIFEST", "").strip()
    assert_no_regression(
        manifest,
        pathlib.Path(previous_setting) if previous_setting else None,
        allow_regression=os.environ.get("CORPUS_BACKUP_ALLOW_REGRESSION", "").lower() == "true",
    )
    atomic_write_json(output_dir / "manifest.json", manifest)
    validate_snapshot(output_dir)
    return manifest


def main() -> int:
    url = os.environ.get("NFL_BACKUP_DATABASE_URL") or os.environ.get("NFL_DATABASE_URL")
    if not url:
        print("ERROR: set NFL_BACKUP_DATABASE_URL or NFL_DATABASE_URL", file=sys.stderr)
        return 1
    if url.startswith("sqlite:"):
        engine = create_engine(url)
    else:
        try:
            require_verified_tls(url)
        except RuntimeError as exc:
            print(f"ERROR: corpus backup configuration rejected: {exc}", file=sys.stderr)
            return 1
        engine = create_engine(
            portable_postgres_url(url),
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
