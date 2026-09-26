#!/usr/bin/env python3
"""Build (or verify) the WNBA race corpus for offline backtest racing.

Issue #337 / parent #332. Full per-slate export (served pool, realized scores,
finishers with raw user_id, field, drafts, shark_priors) lands in a follow-up.
This entry point is the CLI + integrity contract the corpus-backup workflow
calls: ``--seasons``, ``--out``, ``--verify-only``, read-only DB via
``DATABASE_PUBLIC_URL`` (CI maps ``BACKUP_DATABASE_URL``), and a hash-verified
manifest under ``<out>/season=<yyyy>/*.parquet``.

Until the full builder replaces the stub path, a successful DB run writes
schema-only (zero-row) parquet files for each requested season discovered in
``slate_labels``, plus a self-describing manifest. Use ``--stub`` offline to
emit the same layout from fixtures without a database.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
from typing import Any

import pandas as pd
from corpus_backup_common import (
    atomic_write_json,
    portable_postgres_url,
    require_verified_tls,
    sha256_file,
)
from sqlalchemy import create_engine, text

RACE_TABLES: dict[str, tuple[str, ...]] = {
    "served_pool": (
        "season",
        "slate_date",
        "real_sports_player_id",
        "platform_player_id",
        "wnba_player_id",
        "identity_provenance",
        "name",
        "team",
        "opponent",
        "game_id",
        "position",
        "card_boost",
        "section",
        "has_minutes_features",
        "has_props",
        "features_json",
        "captured_at",
    ),
    "realized_scores": (
        "season",
        "slate_date",
        "real_sports_player_id",
        "platform_player_id",
        "wnba_player_id",
        "real_score_leaderboard",
        "real_score_platform",
        "real_score_boxscore",
        "real_score",
        "value_source",
        "played",
    ),
    "finishers": (
        "season",
        "slate_date",
        "contest_id",
        "entry_id",
        "rank",
        "paged_rank",
        "user_id",
        "score",
        "num_brawlers",
        "lineup_json",
        "pick1_player_id",
        "pick1_value",
        "pick1_slot_base",
        "pick1_boost",
        "pick2_player_id",
        "pick2_value",
        "pick2_slot_base",
        "pick2_boost",
        "pick3_player_id",
        "pick3_value",
        "pick3_slot_base",
        "pick3_boost",
        "pick4_player_id",
        "pick4_value",
        "pick4_slot_base",
        "pick4_boost",
        "pick5_player_id",
        "pick5_value",
        "pick5_slot_base",
        "pick5_boost",
        "recomputed_score",
    ),
    "field": (
        "season",
        "slate_date",
        "contest_id",
        "num_brawlers",
        "observed_finishers",
        "rank1_score",
        "rank20_score",
        "theoretical_ceiling",
    ),
    "drafts": (
        "season",
        "slate_date",
        "real_sports_player_id",
        "platform_player_id",
        "drafts",
        "section",
    ),
    "shark_priors": (
        "season",
        "slate_date",
        "real_sports_player_id",
        "shark_prior_draft_rate",
        "shark_prior_n",
        "field_prior_draft_rate",
        "shark_lift",
        "cohort_as_of_n_sharks",
    ),
}

MANIFEST_SCHEMA_VERSION = 1
MAX_PARQUET_BYTES = 100 * 1024 * 1024


class RaceCorpusValidationError(ValueError):
    """A race corpus manifest or parquet payload failed local integrity checks."""


def parse_seasons(raw: str) -> frozenset[str] | None:
    """Parse ``--seasons``: ``all`` means no year filter; otherwise YYYY list."""

    text_value = raw.strip()
    if not text_value:
        raise ValueError("--seasons must be 'all' or a comma-separated YYYY list")
    if text_value.lower() == "all":
        return None
    seasons: set[str] = set()
    for part in text_value.split(","):
        token = part.strip()
        if not token:
            continue
        if not (len(token) == 4 and token.isdigit()):
            raise ValueError(f"invalid season token {token!r}; expected YYYY or 'all'")
        seasons.add(token)
    if not seasons:
        raise ValueError("--seasons must be 'all' or a comma-separated YYYY list")
    return frozenset(seasons)


def in_seasons(slate_date: str, seasons: frozenset[str] | None) -> bool:
    """True when ``slate_date`` belongs to the selected season set (or all)."""

    if seasons is None:
        return True
    return str(slate_date)[:4] in seasons


def empty_frame(table: str) -> pd.DataFrame:
    columns = RACE_TABLES[table]
    return pd.DataFrame({column: pd.Series(dtype="object") for column in columns})


def _season_dir(out_dir: pathlib.Path, season: str) -> pathlib.Path:
    return out_dir / f"season={season}"


def write_season_tables(out_dir: pathlib.Path, season: str) -> dict[str, dict[str, Any]]:
    """Write schema-only parquet files for one season; return manifest details."""

    season_root = _season_dir(out_dir, season)
    season_root.mkdir(parents=True, exist_ok=True)
    details: dict[str, dict[str, Any]] = {}
    for table, columns in RACE_TABLES.items():
        path = season_root / f"{table}.parquet"
        frame = empty_frame(table)
        frame.to_parquet(path, index=False)
        size = path.stat().st_size
        if size > MAX_PARQUET_BYTES:
            raise RuntimeError(f"race parquet over 100MB: {path}")
        relative = f"season={season}/{table}.parquet"
        details[f"{season}/{table}"] = {
            "file": relative,
            "columns": list(columns),
            "rows": 0,
            "bytes": size,
            "sha256": sha256_file(path),
            "season": season,
            "table": table,
        }
        print(f"race stub wrote {relative} ({size} bytes)")
    return details


def build_manifest(
    out_dir: pathlib.Path,
    table_details: dict[str, dict[str, Any]],
    *,
    seasons: list[str],
    stub: bool,
    generated_at: dt.datetime | None = None,
) -> dict[str, Any]:
    timestamp = generated_at or dt.datetime.now(dt.UTC)
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "kind": "wnba_race_corpus",
        "stub": stub,
        "generated_at_utc": timestamp.astimezone(dt.UTC).replace(microsecond=0).isoformat(),
        "transaction": {"isolation": "REPEATABLE READ", "read_only": True},
        "seasons": seasons,
        "tables": table_details,
    }


def verify_race_corpus(out_dir: pathlib.Path) -> dict[str, Any]:
    """Validate manifest shape, byte counts, and SHA-256 hashes for every parquet."""

    manifest_path = out_dir / "manifest.json"
    try:
        decoded = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RaceCorpusValidationError("race corpus manifest could not be read") from exc
    if not isinstance(decoded, dict):
        raise RaceCorpusValidationError("race corpus manifest must be an object")
    if decoded.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise RaceCorpusValidationError("race corpus manifest has an unsupported schema version")
    if decoded.get("kind") != "wnba_race_corpus":
        raise RaceCorpusValidationError("race corpus manifest kind is invalid")
    tables = decoded.get("tables")
    if not isinstance(tables, dict) or not tables:
        raise RaceCorpusValidationError("race corpus manifest tables are missing")
    for key, entry in sorted(tables.items()):
        if not isinstance(entry, dict):
            raise RaceCorpusValidationError(f"race corpus manifest entry for {key} is invalid")
        filename = entry.get("file")
        if not isinstance(filename, str) or not filename.endswith(".parquet"):
            raise RaceCorpusValidationError(f"race corpus file name for {key} is invalid")
        payload = out_dir / filename
        if not payload.is_file():
            raise RaceCorpusValidationError(f"race corpus payload for {key} is missing")
        expected_size = entry.get("bytes")
        if not isinstance(expected_size, int) or expected_size != payload.stat().st_size:
            raise RaceCorpusValidationError(f"race corpus byte count for {key} does not match")
        if expected_size > MAX_PARQUET_BYTES:
            raise RaceCorpusValidationError(f"race corpus payload for {key} exceeds 100MB")
        expected_hash = entry.get("sha256")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise RaceCorpusValidationError(f"race corpus hash for {key} is invalid")
        if sha256_file(payload) != expected_hash:
            raise RaceCorpusValidationError(f"race corpus hash for {key} does not match")
        expected_columns = entry.get("columns")
        table = entry.get("table")
        if isinstance(table, str) and table in RACE_TABLES:
            if expected_columns != list(RACE_TABLES[table]):
                raise RaceCorpusValidationError(f"race corpus columns for {key} are invalid")
    return decoded


def discover_seasons(engine, seasons: frozenset[str] | None) -> list[str]:
    """List distinct calendar seasons present in slate_labels, filtered by --seasons."""

    query = text(
        "select distinct left(slate_date::text, 4) as season "
        "from slate_labels order by season"
    )
    connection = engine.connect().execution_options(isolation_level="REPEATABLE READ")
    try:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            frame = pd.read_sql(query, connection)
    finally:
        connection.close()
    found = [str(value) for value in frame["season"].tolist() if str(value).isdigit()]
    if seasons is not None:
        found = [season for season in found if season in seasons]
    return found


def build_stub_corpus(
    out_dir: pathlib.Path,
    *,
    seasons: list[str],
    stub: bool,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    details: dict[str, dict[str, Any]] = {}
    for season in seasons:
        details.update(write_season_tables(out_dir, season))
    manifest = build_manifest(out_dir, details, seasons=seasons, stub=stub)
    atomic_write_json(out_dir / "manifest.json", manifest)
    verify_race_corpus(out_dir)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build or verify the WNBA race corpus parquet tree (#337)."
    )
    parser.add_argument(
        "--seasons",
        default="all",
        help="Comma-separated YYYY list or 'all' (default: all).",
    )
    parser.add_argument(
        "--out",
        default=os.environ.get("RACE_CORPUS_DIR", "data/race/wnba"),
        help="Output root for season=<yyyy>/*.parquet + manifest.json.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Validate an existing race corpus tree; do not query the database.",
    )
    parser.add_argument(
        "--stub",
        action="store_true",
        help="Write schema-only fixtures without a database (offline / tests).",
    )
    parser.add_argument(
        "--stub-seasons",
        default="2026",
        help="With --stub, seasons to materialize when --seasons is 'all'.",
    )
    args = parser.parse_args(argv)
    out_dir = pathlib.Path(args.out)

    try:
        season_filter = parse_seasons(args.seasons)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.verify_only:
        try:
            manifest = verify_race_corpus(out_dir)
        except RaceCorpusValidationError as exc:
            print(f"ERROR: race corpus verification failed: {exc}", file=sys.stderr)
            return 1
        print(
            "race corpus verified:",
            ", ".join(manifest.get("seasons", [])),
            f"({len(manifest.get('tables', {}))} files)",
        )
        return 0

    if args.stub:
        stub_seasons = list(parse_seasons(args.stub_seasons) or ())
        if season_filter is not None:
            stub_seasons = [season for season in stub_seasons if season in season_filter]
        if not stub_seasons:
            print("ERROR: --stub produced no seasons to write", file=sys.stderr)
            return 1
        try:
            manifest = build_stub_corpus(out_dir, seasons=sorted(stub_seasons), stub=True)
        except Exception as exc:
            print(f"ERROR: race corpus stub failed ({type(exc).__name__})", file=sys.stderr)
            return 1
        print("race corpus stub seasons:", ", ".join(manifest["seasons"]))
        return 0

    url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: set DATABASE_PUBLIC_URL or DATABASE_URL (or pass --stub)", file=sys.stderr)
        return 1
    try:
        require_verified_tls(url)
    except RuntimeError as exc:
        print(f"ERROR: race corpus configuration rejected: {exc}", file=sys.stderr)
        return 1

    engine = create_engine(
        portable_postgres_url(url),
        connect_args={"options": "-c default_transaction_read_only=on"},
    )
    try:
        seasons = discover_seasons(engine, season_filter)
        if not seasons:
            print("ERROR: no slate_labels seasons matched --seasons", file=sys.stderr)
            return 1
        # Stub export: schema-only parquet per season. Full pool/finisher rows
        # land when the #337 builder replaces this path.
        manifest = build_stub_corpus(out_dir, seasons=seasons, stub=True)
    except Exception as exc:
        print(f"ERROR: race corpus build failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    print("race corpus stub seasons:", ", ".join(manifest["seasons"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
