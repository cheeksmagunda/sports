"""Backfill contest_placements for all historical slates with frozen lineups.

Runs the same auto_record_from_dayclose logic that job_dayclose now does
automatically, against all 18 slates where we have a frozen lineup + real
scores + leaderboard captures.

Usage:
  DATABASE_URL=$DATABASE_PUBLIC_URL uv run python scripts/backfill_placements.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wnba_oracle.picker.optimize import DEFAULT_SLOT_MULTIPLIERS


def main() -> int:
    from sqlalchemy import text

    from wnba_oracle.db.engine import get_engine
    from wnba_oracle.db.reads import read_leaderboards, read_slate_labels
    from wnba_oracle.scheduler.placements import auto_record_from_dayclose

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL required")
        return 1

    print("Loading data...")
    sl = read_slate_labels()
    lb = read_leaderboards()

    engine = get_engine()
    with engine.connect() as conn:
        # All dates with frozen lineups
        frozen_dates = conn.execute(
            text("SELECT DISTINCT slate_date FROM frozen_lineups ORDER BY slate_date")
        ).fetchall()
        frozen_dates_set = {str(r[0]) for r in frozen_dates}
        print(f"Found {len(frozen_dates_set)} dates with frozen lineups")

        results = []
        for sd in sorted(frozen_dates_set):
            sl_s = sl.filter(pl.col("slate_date") == sd)
            lb_s = lb.filter(pl.col("slate_date") == sd)
            if sl_s.height == 0 or lb_s.height == 0:
                print(f"  {sd}: no labels or leaderboard, skip")
                continue

            rs_by_pid: dict[int, float] = {}
            boost_by_pid: dict[int, float] = {}
            for r in sl_s.iter_rows(named=True):
                pid = int(r["platform_player_id"])
                rs = r["real_score"]
                rs_by_pid[pid] = float(rs) if rs is not None else 0.0
                boost_by_pid[pid] = float(r["card_boost"])

            row = conn.execute(
                text("SELECT lineup FROM frozen_lineups WHERE slate_date = :sd ORDER BY id DESC LIMIT 1"),
                {"sd": sd},
            ).first()
            if row is None:
                continue

            lineup_json = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            player_ids = [int(p) for p in lineup_json.get("player_ids", [])]
            if not player_ids:
                continue

            members = sorted(
                ((pid, rs_by_pid.get(pid, 0.0)) for pid in player_ids),
                key=lambda x: -x[1],
            )
            our_score = sum(
                (DEFAULT_SLOT_MULTIPLIERS[i] + boost_by_pid.get(pid, 0.0)) * rs
                for i, (pid, rs) in enumerate(members)
            )

            lb_scores = lb_s["score"].to_list()
            contest_ids = lb_s["contest_id"].unique().to_list()
            contest_id = int(contest_ids[0]) if contest_ids else 0

            total_drafts = sum(r["drafts"] or 0 for r in sl_s.iter_rows(named=True) if r.get("drafts"))
            actual_own: dict[int, float] | None = None
            if total_drafts > 0:
                actual_own = {
                    int(r["platform_player_id"]): float(r["drafts"] or 0) / total_drafts
                    for r in sl_s.iter_rows(named=True)
                }

            result = auto_record_from_dayclose(
                conn,
                slate_date=sd,
                entry_score=our_score,
                leaderboard_scores=lb_scores,
                contest_id=contest_id,
                actual_ownership=actual_own,
            )

            if result is None:
                print(f"  {sd}: skipped (no frozen lineup snapshot)")
            else:
                n_above = sum(1 for s in lb_scores if s > our_score)
                rank_str = f"rank {n_above + 1}/{len(lb_scores)} in top-20"
                print(f"  {sd}: score={our_score:.2f}  {rank_str}  contest={contest_id}")
                results.append({"date": sd, "our_score": our_score, "rank_in_top20": n_above + 1})

        conn.commit()

    print(f"\nBackfilled {len(results)} placement records.")
    if results:
        import numpy as np
        ranks = [r["rank_in_top20"] for r in results]
        scores = [r["our_score"] for r in results]
        n_beats_median = sum(1 for r in ranks if r <= 10)
        n_beats_top5 = sum(1 for r in ranks if r <= 5)
        n_beats_top1 = sum(1 for r in ranks if r == 1)
        print(f"\nRelative placement in captured top-20 ({len(results)} slates):")
        print(f"  Beat top-20 median (<=10): {n_beats_median}/{len(results)} ({100*n_beats_median/len(results):.0f}%)")
        print(f"  Beat top-5:                {n_beats_top5}/{len(results)} ({100*n_beats_top5/len(results):.0f}%)")
        print(f"  Beat top-1 (won contest):  {n_beats_top1}/{len(results)} ({100*n_beats_top1/len(results):.0f}%)")
        print(f"  Median lineup score:       {np.median(scores):.2f}")
        print(f"  Mean rank in top-20:       {np.mean(ranks):.1f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
