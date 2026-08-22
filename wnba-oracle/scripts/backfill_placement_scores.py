"""Recompute contest_placements.entry_score under the committed slot order.

Until 2026-08-19 dayclose ranked the five picks by realized score before
applying the slot multipliers, awarding the 2.0x base to whoever spiked. The
slot order is committed before tip, so the stored number is an upper bound, not
our result. See job_dayclose._auto_record_placement and commit 4f73668.

This rewrites the affected columns for rows written before the fix. entry_rank
and entry_count move with the score, and are recomputed by calling
scheduler.placements.derive_placement_fields -- the same function
auto_record_from_dayclose uses, not a copy of it. cashed is deliberately NOT
touched: it keys off payout_received_cents, which is NULL on every auto-recorded
row and is operator-supplied, not derivable from the score.

DRY RUN BY DEFAULT. It prints the before/after table and writes nothing unless
--apply is passed. With --apply the UPDATE runs in a single transaction.

Rows whose frozen lineup or slate_labels are missing cannot be recomputed and
are reported as skipped rather than zeroed.

Usage:
    scripts/with-secrets wnba-oracle -- uv run --package wnba-oracle \
      python scripts/backfill_placement_scores.py
    scripts/with-secrets wnba-oracle -- uv run --package wnba-oracle \
      python scripts/backfill_placement_scores.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.engine import Connection, Engine  # noqa: E402

from wnba_oracle.common.db_utils import repair_local_sslrootcert  # noqa: E402
from wnba_oracle.db.engine import normalize_postgres_url  # noqa: E402
from wnba_oracle.eval.contest_score import (  # noqa: E402
    DEFAULT_SLOT_BASES,
    committed_order_score,
)
from wnba_oracle.scheduler.placements import derive_placement_fields  # noqa: E402

# cron-dayclose picked up the fix at this deploy (commit 4f73668). A bare date
# would wrongly exempt the 2026-08-18 row, which dayclose recorded at 06:00 UTC
# on 2026-08-19, still on the old code.
FIX_DATE = "2026-08-19T22:29:16Z"


def _placement_update(conn: Connection, row: dict) -> tuple[dict | None, str | None]:
    slate = str(row["slate_date"])
    frozen = conn.execute(
        sa.text(
            "SELECT lineup FROM frozen_lineups WHERE slate_date = :sd ORDER BY id DESC LIMIT 1"
        ),
        {"sd": slate},
    ).first()
    if frozen is None:
        return None, "no frozen lineup"
    lineup = frozen[0] if isinstance(frozen[0], dict) else json.loads(frozen[0])
    pids = [int(pid) for pid in lineup.get("player_ids", [])]
    if len(pids) != len(DEFAULT_SLOT_BASES):
        return None, f"{len(pids)} players in frozen lineup"

    labels = {
        int(label["platform_player_id"]): (
            float(label["real_score"] or 0.0),
            float(label["card_boost"] or 0.0),
        )
        for label in conn.execute(
            sa.text(
                "SELECT platform_player_id, real_score, card_boost "
                "FROM slate_labels WHERE slate_date = :sd"
            ),
            {"sd": slate},
        ).mappings()
    }
    missing = [pid for pid in pids if pid not in labels]
    if missing:
        return None, f"{len(missing)} picks lack slate_labels"

    new_score = committed_order_score(
        [labels[pid][0] for pid in pids], [labels[pid][1] for pid in pids]
    )
    board = [
        float(item[0])
        for item in conn.execute(
            sa.text(
                "SELECT score FROM contest_leaderboards WHERE slate_date = :sd "
                "ORDER BY rank ASC LIMIT 20"
            ),
            {"sd": slate},
        ).all()
    ]
    field_size = conn.execute(
        sa.text("SELECT max(num_brawlers) FROM contest_leaderboards WHERE slate_date = :sd"),
        {"sd": slate},
    ).scalar()
    rank, count, _ = derive_placement_fields(
        entry_score=new_score,
        leaderboard_scores=board,
        field_size=int(field_size) if field_size else None,
    )
    percentile = (rank / count) if (rank is not None and count) else None
    return {
        "slate_date": slate,
        "old_score": float(row["entry_score"]) if row["entry_score"] is not None else None,
        "entry_score": new_score,
        "old_rank": row["entry_rank"],
        "entry_rank": rank,
        "entry_count": count,
        "finish_percentile": percentile,
        "top_10pct": bool(percentile is not None and percentile <= 0.10),
        "top_1pct": bool(percentile is not None and percentile <= 0.01),
    }, None


def _collect_updates(engine: Engine) -> tuple[list[dict], list[tuple[str, str]]]:
    updates: list[dict] = []
    skipped: list[tuple[str, str]] = []
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT slate_date, entry_score, entry_rank, entry_count, finish_percentile "
                "FROM contest_placements WHERE recorded_at < :fix ORDER BY slate_date"
            ),
            {"fix": FIX_DATE},
        ).mappings()
        for row in rows:
            update, reason = _placement_update(conn, dict(row))
            if update is not None:
                updates.append(update)
            elif reason is not None:
                skipped.append((str(row["slate_date"]), reason))
    return updates, skipped


def _print_summary(updates: list[dict], skipped: list[tuple[str, str]]) -> None:

    print(
        f"{'slate':12s} {'old score':>9s} {'new score':>9s} {'delta':>7s} "
        f"{'old rank':>8s} {'new rank':>8s}"
    )
    for u in updates:
        old = u["old_score"]
        delta = (u["entry_score"] - old) if old is not None else float("nan")
        print(
            f"{u['slate_date']:12s} {old if old is None else round(old, 2)!s:>9s} "
            f"{u['entry_score']:9.2f} {delta:+7.2f} "
            f"{u['old_rank']!s:>8s} {u['entry_rank']!s:>8s}"
        )
    for slate, why in skipped:
        print(f"  skipped {slate}: {why}")
    print(f"\n{len(updates)} rows recomputable, {len(skipped)} skipped")
    if updates:
        deltas = [u["entry_score"] - u["old_score"] for u in updates if u["old_score"] is not None]
        if deltas:
            print(f"mean change {sum(deltas) / len(deltas):+.3f}, most negative {min(deltas):+.3f}")


def _apply_updates(engine: Engine, updates: list[dict]) -> None:
    with engine.begin() as conn:
        for update in updates:
            conn.execute(
                sa.text(
                    "UPDATE contest_placements SET entry_score = :entry_score, "
                    "entry_rank = :entry_rank, entry_count = :entry_count, "
                    "finish_percentile = :finish_percentile, "
                    "top_10pct = :top_10pct, top_1pct = :top_1pct "
                    "WHERE slate_date = :slate_date"
                ),
                {
                    key: value
                    for key, value in update.items()
                    if key not in ("old_score", "old_rank")
                },
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set")

    connect_args = {} if args.apply else {"options": "-c default_transaction_read_only=on"}
    repaired_url = repair_local_sslrootcert(url, REPO_ROOT)
    engine = sa.create_engine(normalize_postgres_url(repaired_url), connect_args=connect_args)
    updates, skipped = _collect_updates(engine)
    _print_summary(updates, skipped)
    if not args.apply:
        print("\nDRY RUN. Nothing written. Re-run with --apply to commit.")
        return 0

    _apply_updates(engine, updates)
    print(f"\nAPPLIED to {len(updates)} rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
