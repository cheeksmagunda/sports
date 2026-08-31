"""Backfill player_slate_ownership.actual_* from existing slate_labels.drafts.

## Why

`player_slate_ownership` (D90 migration) has been empty in production: the
per-player actual-ownership computation already existed in
`job_dayclose._auto_record_placement` (feeding `contest_placements`'s JSONB
blob), but nothing wrote it into the dedicated per-player table the
calibration loop (`placements_calibration.ownership_log_loss_by_decile`)
reads. That gap is now closed going forward (day-close upserts it after
every slate). This script closes it for the past: every slate that already
has `slate_labels.drafts` values but no `player_slate_ownership` row gets one,
using the exact same normalization `record_actual_ownership` uses (shares
sum to 1 across labeled players, matching `project_ownership`'s scale).

This does not touch `projected_ownership` -- there is no historical field-model
snapshot to backfill; projections start accumulating from the freeze this
change ships in.

## Safety

Read-only by default (reports what it would write). Requires `--execute` to
write. Purely additive: player_slate_ownership was empty, so this can only
insert new rows (it upserts by (slate_date, player_id), so re-running is
idempotent) -- there is no existing data to lose.

Reads the connection from DATABASE_PUBLIC_URL (read-only-friendly, sslmode
verify-ca) or, as a fallback, DATABASE_URL, matching backup_corpus.py.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

from corpus_backup_common import portable_postgres_url, require_verified_tls
from sqlalchemy import create_engine, text

SELECT_LABELS = text(
    "SELECT slate_date, platform_player_id, drafts FROM slate_labels "
    "WHERE drafts IS NOT NULL AND drafts > 0 "
    "AND (CAST(:slate_date AS VARCHAR) IS NULL OR slate_date = CAST(:slate_date AS VARCHAR)) "
    "ORDER BY slate_date"
)

SELECT_EXISTING = text(
    "SELECT DISTINCT slate_date FROM player_slate_ownership WHERE actual_ownership IS NOT NULL"
)

UPSERT = text(
    """
    INSERT INTO player_slate_ownership (
        slate_date, player_id, actual_ownership, actual_drafts, updated_at
    ) VALUES (
        :slate_date, :player_id, :actual_ownership, :actual_drafts, now()
    )
    ON CONFLICT (slate_date, player_id) DO UPDATE SET
        actual_ownership = EXCLUDED.actual_ownership,
        actual_drafts = EXCLUDED.actual_drafts,
        updated_at = now()
    """
)


def plan_backfill(
    label_rows: list[tuple[str, int, int]], already_done: set[str]
) -> dict[str, dict[int, tuple[float, int]]]:
    """Return {slate_date: {player_id: (ownership_share, drafts)}} for slates
    not already in player_slate_ownership. ``label_rows`` is
    (slate_date, platform_player_id, drafts) tuples."""
    by_slate: dict[str, dict[int, int]] = defaultdict(dict)
    for slate_date, player_id, drafts in label_rows:
        if slate_date in already_done:
            continue
        by_slate[slate_date][int(player_id)] = int(drafts)

    plan: dict[str, dict[int, tuple[float, int]]] = {}
    for slate_date, drafts_by_pid in by_slate.items():
        total = sum(drafts_by_pid.values())
        if total <= 0:
            continue
        plan[slate_date] = {pid: (drafts / total, drafts) for pid, drafts in drafts_by_pid.items()}
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
        help="Actually write the backfilled rows. Default is dry-run/report-only.",
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
            label_rows = [
                (str(r[0]), int(r[1]), int(r[2]))
                for r in conn.execute(SELECT_LABELS, {"slate_date": args.slate_date})
            ]
            already_done = {str(r[0]) for r in conn.execute(SELECT_EXISTING)}

        plan = plan_backfill(label_rows, already_done)
        n_rows = sum(len(v) for v in plan.values())
        print(
            f"backfill plan: {n_rows} player row(s) across {len(plan)} slate(s) "
            f"not yet in player_slate_ownership"
        )
        for slate_date in sorted(plan)[:10]:
            print(f"  {slate_date}: {len(plan[slate_date])} player(s)")
        if len(plan) > 10:
            print(f"  ... and {len(plan) - 10} more slate(s)")

        if not args.execute:
            print("dry run only; pass --execute to write these rows")
            return 0

        if n_rows == 0:
            print("nothing to write")
            return 0

        n_written = 0
        with engine.begin() as conn:
            for slate_date, by_pid in plan.items():
                for player_id, (ownership, drafts) in by_pid.items():
                    conn.execute(
                        UPSERT,
                        {
                            "slate_date": slate_date,
                            "player_id": player_id,
                            "actual_ownership": ownership,
                            "actual_drafts": drafts,
                        },
                    )
                    n_written += 1
        print(f"backfilled actual_ownership on {n_written} row(s) across {len(plan)} slate(s)")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
