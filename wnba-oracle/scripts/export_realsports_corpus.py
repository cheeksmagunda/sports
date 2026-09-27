#!/usr/bin/env python3
"""Export WNBA slate_labels + contest_leaderboards into corpus layout (#526).

Layout under ``{corpus-root}/sport=wnba/season=YYYY/slate=DATE/``:

- ``total_value_leaderboard.json`` (section=highestBoostedValuePlayers)
- ``draft_stats_all_sections.jsonl``
- ``lineups_top20.json`` (leaderboards as recorded_states)
- ``manifest.json`` (shard)

Prefer ``DATABASE_PUBLIC_URL`` / ``DATABASE_URL`` from the process environment
(Codespace/Railway via ``scripts/codespace-railway-env``). With ``--dry-run``,
writes schema-faithful demo rows and never opens a database.

Never prints connection URLs or secret values.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from pathlib import Path

# scripts/ sits on sys.path when invoked as ``python scripts/...``.
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from corpus_backup_common import portable_postgres_url  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

from wnba_oracle.corpus.realsports_export import (  # noqa: E402
    export_slates,
    fake_demo_rows,
    load_rows_from_engine,
)

ALLOWED_SSLMODES = frozenset({"require", "verify-ca", "verify-full"})


def _require_tls(url: str) -> None:
    """Accept Railway public-proxy ``require`` plus verified modes; never print URL."""

    parsed = urllib.parse.urlsplit(url)
    query = {
        name.lower(): value.lower()
        for name, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    }
    mode = query.get("sslmode", "")
    if mode not in ALLOWED_SSLMODES:
        raise RuntimeError("database URL must use sslmode=require, verify-ca, or verify-full")


def _resolve_database_url() -> str | None:
    for key in ("DATABASE_PUBLIC_URL", "DATABASE_URL", "BACKUP_DATABASE_URL"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


def _summarize(summaries: list) -> dict[str, object]:
    return {
        "slates": len(summaries),
        "hv_rows": sum(s.hv_rows for s in summaries),
        "draft_stats_rows": sum(s.draft_stats_rows for s in summaries),
        "lineup_rows": sum(s.lineup_rows for s in summaries),
        "paths": [s.path for s in summaries[:5]],
        "truncated_paths": max(0, len(summaries) - 5),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=Path(os.environ.get("REALSPORTS_CORPUS_ROOT", "corpus")),
        help="Output root (sibling corpus checkout or gitignored monorepo corpus/)",
    )
    parser.add_argument(
        "--slate-date",
        action="append",
        dest="slate_dates",
        default=None,
        help="Limit to one or more YYYY-MM-DD slates (repeatable). Default: all.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write fake demo rows; do not open DATABASE_URL.",
    )
    args = parser.parse_args(argv)

    corpus_root = args.corpus_root.resolve()
    corpus_root.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        labels, boards = fake_demo_rows()
        mode = "dry-run"
    else:
        url = _resolve_database_url()
        if not url:
            print(
                "ERROR: set DATABASE_PUBLIC_URL, DATABASE_URL, or BACKUP_DATABASE_URL "
                "(or pass --dry-run)",
                file=sys.stderr,
            )
            return 1
        try:
            _require_tls(url)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        engine = create_engine(
            portable_postgres_url(url),
            connect_args={"options": "-c default_transaction_read_only=on"},
        )
        try:
            labels, boards = load_rows_from_engine(engine)
        except Exception as exc:
            print(
                f"ERROR: corpus export query failed ({type(exc).__name__})",
                file=sys.stderr,
            )
            return 1
        finally:
            engine.dispose()
        mode = "live"

    summaries = export_slates(
        corpus_root,
        label_rows=labels,
        leaderboard_rows=boards,
        slate_dates=args.slate_dates,
    )
    summary = _summarize(summaries)
    summary["mode"] = mode
    summary["corpus_root"] = str(corpus_root)
    summary["label_rows_loaded"] = len(labels)
    summary["leaderboard_rows_loaded"] = len(boards)
    print(json.dumps(summary, sort_keys=True))
    if mode == "live" and not summaries:
        print("ERROR: live export produced zero slate shards", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
