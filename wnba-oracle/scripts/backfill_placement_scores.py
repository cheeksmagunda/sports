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
    export DATABASE_URL=...
    uv run --extra dev python scripts/backfill_placement_scores.py
    uv run --extra dev python scripts/backfill_placement_scores.py --apply
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


def _load_env() -> None:
    env = REPO_ROOT / ".env"
    if os.environ.get("DATABASE_URL") or not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.strip().strip('"').strip("'")
        if key.strip() == "DATABASE_PUBLIC_URL" and val:
            os.environ.setdefault("DATABASE_URL", val)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    args = ap.parse_args()

    _load_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set")

    # Read-only guard unless --apply, so a dry run cannot write even by mistake.
    connect_args = {} if args.apply else {"options": "-c default_transaction_read_only=on"}
    engine = sa.create_engine(normalize_postgres_url(url), connect_args=connect_args)

    updates: list[dict] = []
    skipped: list[tuple[str, str]] = []
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT slate_date, entry_score, entry_rank, entry_count, finish_percentile "
                "FROM contest_placements WHERE recorded_at < :fix ORDER BY slate_date"
            ),
            {"fix": FIX_DATE},
        ).mappings().all()

        for r in rows:
            slate = str(r["slate_date"])
            frozen = conn.execute(
                sa.text(
                    "SELECT lineup FROM frozen_lineups WHERE slate_date = :sd "
                    "ORDER BY id DESC LIMIT 1"
                ),
                {"sd": slate},
            ).first()
            if frozen is None:
                skipped.append((slate, "no frozen lineup"))
                continue
            lineup = frozen[0] if isinstance(frozen[0], dict) else json.loads(frozen[0])
            pids = [int(p) for p in lineup.get("player_ids", [])]
            if len(pids) != len(DEFAULT_SLOT_BASES):
                skipped.append((slate, f"{len(pids)} players in frozen lineup"))
                continue

            labels = {
                int(x["platform_player_id"]): (
                    float(x["real_score"] or 0.0),
                    float(x["card_boost"] or 0.0),
                )
                for x in conn.execute(
                    sa.text(
                        "SELECT platform_player_id, real_score, card_boost "
                        "FROM slate_labels WHERE slate_date = :sd"
                    ),
                    {"sd": slate},
                ).mappings()
            }
            missing = [p for p in pids if p not in labels]
            if missing:
                skipped.append((slate, f"{len(missing)} picks lack slate_labels"))
                continue

            new_score = committed_order_score(
                [labels[p][0] for p in pids], [labels[p][1] for p in pids]
            )
            board = [
                float(x[0])
                for x in conn.execute(
                    sa.text(
                        "SELECT score FROM contest_leaderboards WHERE slate_date = :sd "
                        "ORDER BY rank ASC LIMIT 20"
                    ),
                    {"sd": slate},
                ).all()
            ]
            field_size = conn.execute(
                sa.text(
                    "SELECT max(num_brawlers) FROM contest_leaderboards WHERE slate_date = :sd"
                ),
                {"sd": slate},
            ).scalar()
            rank, count, _meta = derive_placement_fields(
                entry_score=new_score,
                leaderboard_scores=board,
                field_size=int(field_size) if field_size else None,
            )
            pct = (rank / count) if (rank is not None and count) else None
            updates.append(
                {
                    "slate_date": slate,
                    "old_score": float(r["entry_score"]) if r["entry_score"] is not None else None,
                    "entry_score": new_score,
                    "old_rank": r["entry_rank"],
                    "entry_rank": rank,
                    "entry_count": count,
                    "finish_percentile": pct,
                    "top_10pct": bool(pct is not None and pct <= 0.10),
                    "top_1pct": bool(pct is not None and pct <= 0.01),
                }
            )

    print(f"{'slate':12s} {'old score':>9s} {'new score':>9s} {'delta':>7s} "
          f"{'old rank':>8s} {'new rank':>8s}")
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
            print(f"mean change {sum(deltas) / len(deltas):+.3f}, "
                  f"most negative {min(deltas):+.3f}")

    if not args.apply:
        print("\nDRY RUN. Nothing written. Re-run with --apply to commit.")
        return 0

    with engine.begin() as conn:
        for u in updates:
            conn.execute(
                sa.text(
                    "UPDATE contest_placements SET entry_score = :entry_score, "
                    "entry_rank = :entry_rank, entry_count = :entry_count, "
                    "finish_percentile = :finish_percentile, "
                    "top_10pct = :top_10pct, top_1pct = :top_1pct "
                    "WHERE slate_date = :slate_date"
                ),
                {k: v for k, v in u.items() if k not in ("old_score", "old_rank")},
            )
    print(f"\nAPPLIED to {len(updates)} rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
