"""Backfill missing job1_enrichment.features_json.game_id from same-slate rows.

## Why (issue #32, suggestion 4)

``picker.stacking.resolve_game_keys`` prefers the provider ``game_id`` over
the ``team``/``opponent`` fallback, and for good reason: ``opponent`` can be
silently overwritten with a team's *next* fixture when a post-tip re-capture
picks it up from the Odds API (the #32 corruption). ``game_id`` does not have
that failure mode -- it is written once from the Real Sports payload and
never derived from a team-name map. Rows that are missing ``game_id`` (an
early capture before the provider attached it, or a slate predating D107's
identity export) fall back to the corruptible path. Backfilling ``game_id``
where it is absent, using only data already in the corpus, makes the
fallback path unreachable for those rows.

## What this does, and does not, do

For each slate_date, this correlates rows that already carry a ``game_id``
with rows that are missing one, using ``game_start_utc`` as the join key (two
rows in the same game share the same captured tip time). A row is only
patched when its ``game_start_utc`` maps to *exactly one* distinct
``game_id`` among that slate's already-identified rows -- any ambiguity
(zero or multiple candidate game_ids for a start time) is skipped, not
guessed.

This makes no live provider calls (unlike ``job1.run_game_starts``, which
fetches *today's* live game context and cannot retroactively answer for a
past slate) and never touches ``team``/``opponent`` -- only the
``features_json.game_id`` field, merged in with the same
``features_json || jsonb`` pattern job1 itself uses for patches.

## Safety

Defaults to a dry run that only reports what it would do. Writing requires
the explicit ``--execute`` flag, still runs inside one transaction, and
prints per-slate counts before and after. This script mutates production
data and must not be run without separate operator authorization; do not
wire it into any cron job.

Reads the connection from DATABASE_PUBLIC_URL (read-only, sslmode=verify-ca)
or, as a fallback, DATABASE_URL, matching backup_corpus.py's conventions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

from corpus_backup_common import portable_postgres_url, require_verified_tls
from sqlalchemy import create_engine, text

SELECT_ROWS = text(
    "SELECT id, slate_date, features_json->>'game_id' AS game_id, "
    "features_json->>'game_start_utc' AS game_start_utc "
    "FROM job1_enrichment "
    "WHERE (:slate_date IS NULL OR slate_date = :slate_date) "
    "ORDER BY slate_date, id"
)

PATCH_GAME_ID = text(
    "UPDATE job1_enrichment SET features_json = features_json || CAST(:patch AS jsonb) "
    "WHERE id = :id"
)


def plan_backfill(rows: list[tuple]) -> dict[str, list[tuple[int, str]]]:
    """Return {slate_date: [(row_id, game_id_to_write), ...]} for unambiguous rows.

    ``rows`` is (id, slate_date, game_id, game_start_utc) tuples, one per
    job1_enrichment row, for one or more slates.
    """
    by_slate: dict[str, list[tuple]] = defaultdict(list)
    for row in rows:
        by_slate[row[1]].append(row)

    plan: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for slate_date, slate_rows in by_slate.items():
        candidates: dict[str, set[str]] = defaultdict(set)
        missing: list[tuple[int, str]] = []
        for row_id, _sd, game_id, game_start_utc in slate_rows:
            if not game_start_utc:
                continue
            if game_id:
                candidates[game_start_utc].add(game_id)
            else:
                missing.append((row_id, game_start_utc))
        for row_id, game_start_utc in missing:
            ids = candidates.get(game_start_utc)
            if ids and len(ids) == 1:
                plan[slate_date].append((row_id, next(iter(ids))))
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slate-date",
        default=None,
        help="Restrict to one slate_date (YYYY-MM-DD); default is every slate.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually write the backfilled game_id values. Default is dry-run/report-only.",
    )
    args = parser.parse_args(argv)

    url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: set DATABASE_PUBLIC_URL or DATABASE_URL", file=sys.stderr)
        return 1
    try:
        require_verified_tls(url)
    except RuntimeError as exc:
        print(f"ERROR: backfill configuration rejected: {exc}", file=sys.stderr)
        return 1

    engine = create_engine(portable_postgres_url(url))
    try:
        with engine.connect() as conn:
            rows = list(conn.execute(SELECT_ROWS, {"slate_date": args.slate_date}))

        plan = plan_backfill(rows)
        n_planned = sum(len(v) for v in plan.values())
        print(
            f"backfill plan: {n_planned} row(s) across {len(plan)} slate(s) "
            f"have an unambiguous game_id candidate"
        )
        for slate_date in sorted(plan):
            print(f"  {slate_date}: {len(plan[slate_date])} row(s)")

        if not args.execute:
            print("dry run only; pass --execute to write these values")
            return 0

        if n_planned == 0:
            print("nothing to write")
            return 0

        n_written = 0
        with engine.begin() as conn:
            for slate_rows in plan.values():
                for row_id, game_id in slate_rows:
                    conn.execute(
                        PATCH_GAME_ID,
                        {"id": row_id, "patch": json.dumps({"game_id": game_id})},
                    )
                    n_written += 1
        print(f"backfilled game_id on {n_written} row(s)")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
