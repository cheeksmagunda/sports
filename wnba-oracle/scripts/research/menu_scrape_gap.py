"""R6 menu-scrape gap audit (D72).

Two distinct universes:

1. ``slate_labels`` (contest-stats endpoint): only the THREE highlighted
   sections (``highestBoostedValuePlayers``, ``mostCommon3xPlayers``,
   ``popularPlayers``); ~20-37 players per slate. Stored for ALL 141 slates
   in the historical corpus but it is the wrong reference point for the
   "could the optimizer have picked this player" question -- the live picker
   reads the full ~80-90-player pool from job1_enrichment.

2. ``job1_enrichment.features_json["pool"]`` (live collector): the full a-z
   prefix-iterated rated pool intersected with per-game rosters. Only exists
   for the LIVE collector window (2026-05-26 onward). This is the optimizer's
   true universe.

The audit checks both. The historical (slate_labels) view answers "is the
contest-stats endpoint capturing the full menu?" -- which it never does.
The live (job1_enrichment) view answers "is the prefix-iterated pool scrape
missing any drafted player?" -- if YES, that is a real bug we can fix.

Output:
- console summary
- ``research/internal/_menu_scrape_gap_labels.csv`` (historical view)
- ``research/internal/_menu_scrape_gap_pool.csv`` (live view, the real bug)

Run with the laptop's read-only role (DATABASE_PUBLIC_URL must be set).
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import sqlalchemy as sa  # noqa: E402

from wnba_oracle.common.db_utils import normalize_postgres_url  # noqa: E402
from wnba_oracle.db.reads import read_leaderboards, read_slate_labels  # noqa: E402


def _build_engine() -> sa.Engine:
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL or DATABASE_PUBLIC_URL must be set")
    return sa.create_engine(normalize_postgres_url(db_url), future=True, pool_pre_ping=True)


def _read_live_pool_by_slate(eng: sa.Engine) -> dict[str, set[int]]:
    """Per-slate optimizer pool from job1_enrichment (live collector window)."""
    out: dict[str, set[int]] = defaultdict(set)
    with eng.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT slate_date, real_sports_player_id FROM job1_enrichment "
                "WHERE slate_date >= '2026-05-26'"
            )
        ).fetchall()
    for r in rows:
        sd = str(r[0])
        try:
            pid = int(r[1])
        except (TypeError, ValueError):
            continue
        out[sd].add(pid)
    return out


def main() -> int:
    try:
        eng = _build_engine()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    lb = read_leaderboards(engine=eng)
    sl = read_slate_labels(engine=eng)
    pool_by_slate = _read_live_pool_by_slate(eng)
    print(
        f"leaderboards rows={len(lb)} slate_labels rows={len(sl)} "
        f"live pool slates={len(pool_by_slate)}"
    )

    # Index slate_labels by (slate_date, player_id). slate_labels uses
    # platform_player_id which is the same as lineup_json's playerId.
    labels_by_slate: dict[str, set[int]] = defaultdict(set)
    for row in sl.iter_rows(named=True):
        sd = str(row["slate_date"])
        pid = row.get("platform_player_id")
        if pid is not None:
            labels_by_slate[sd].add(int(pid))

    # Walk every top-20 lineup. For each pick whose playerId is NOT in
    # labels_by_slate[slate_date], record the gap. We also tag whether the
    # pick is in the live pool (when available) -- a "True bug" pick is one
    # that's missing from BOTH slate_labels AND the live pool.
    gaps_labels: list[dict] = []  # historical view (always recorded)
    gaps_pool: list[dict] = []  # live view (only for slates with pool data)
    affected_slates_labels: set[str] = set()
    affected_slates_pool: set[str] = set()
    slates_seen: set[str] = set()
    for row in lb.iter_rows(named=True):
        sd = str(row["slate_date"])
        slates_seen.add(sd)
        try:
            picks = json.loads(row["lineup_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(picks, list):
            continue
        menu = labels_by_slate.get(sd, set())
        pool = pool_by_slate.get(sd, set())
        for p in picks:
            pid = p.get("playerId") or p.get("id")
            if pid is None:
                continue
            try:
                pid_int = int(pid)
            except (TypeError, ValueError):
                continue
            record = {
                "slate_date": sd,
                "contest_id": row.get("contest_id"),
                "missing_player_id": pid_int,
                "missing_display_name": p.get("displayName") or "",
                "winning_rank": row.get("rank"),
                "winning_score": row.get("score"),
                "mult": p.get("multiplier"),
                "mult_score": p.get("score"),
            }
            if menu and pid_int not in menu:
                gaps_labels.append(record)
                affected_slates_labels.add(sd)
            if pool and pid_int not in pool:
                gaps_pool.append(record)
                affected_slates_pool.add(sd)

    print("\n=== HISTORICAL view (slate_labels = 3 highlighted sections) ===")
    n_slates_with_menu = len(set(labels_by_slate.keys()) & slates_seen)
    print(
        f"slates with leaderboard data={len(slates_seen)} "
        f"with menu data={n_slates_with_menu} "
        f"with at-least-one missing pick={len(affected_slates_labels)} "
        f"({len(affected_slates_labels) / max(1, n_slates_with_menu):.1%})"
    )
    print(f"total missing-pick rows={len(gaps_labels)}")
    print(
        "NOTE: slate_labels only stores the 3 highlighted Real Sports sections; "
        "the optimizer reads the full a-z pool from job1_enrichment so this view "
        "OVER-counts the real menu gap."
    )

    print("\n=== LIVE view (job1_enrichment pool, the optimizer's actual universe) ===")
    n_slates_with_pool = len(pool_by_slate)
    print(
        f"live slates with pool data={n_slates_with_pool} "
        f"with at-least-one missing pick={len(affected_slates_pool)} "
        f"({len(affected_slates_pool) / max(1, n_slates_with_pool):.1%})"
    )
    print(f"total missing-pick rows (live)={len(gaps_pool)}")

    if gaps_pool:
        per_slate_pool: dict[str, dict] = defaultdict(
            lambda: {"missing_pids": set(), "best_winning_rank": 99}
        )
        for g in gaps_pool:
            sd = g["slate_date"]
            per_slate_pool[sd]["missing_pids"].add(g["missing_player_id"])
            wr = g["winning_rank"]
            if wr is not None and wr < per_slate_pool[sd]["best_winning_rank"]:
                per_slate_pool[sd]["best_winning_rank"] = wr
        print("\nLIVE slates with at-least-one missing pick:")
        print(f"  {'slate_date':<12} {'best_rank':>10} {'distinct_pids':>14}")
        rows_sorted = sorted(
            per_slate_pool.items(),
            key=lambda kv: (kv[1]["best_winning_rank"], -len(kv[1]["missing_pids"])),
        )
        for sd, info in rows_sorted:
            print(
                f"  {sd:<12} {info['best_winning_rank']:>10} {len(info['missing_pids']):>14}"
            )
    else:
        print("\nNo live-pool gaps. The optimizer's pool covered every top-20 winning pick on every live slate.")

    out_dir = ROOT / "research" / "internal"
    out_dir.mkdir(parents=True, exist_ok=True)
    if gaps_labels:
        out_path = out_dir / "_menu_scrape_gap_labels.csv"
        with out_path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(gaps_labels[0].keys()))
            writer.writeheader()
            for g in gaps_labels:
                writer.writerow(g)
        print(f"\nCSV (historical view): {out_path} ({len(gaps_labels)} rows)")
    if gaps_pool:
        out_path = out_dir / "_menu_scrape_gap_pool.csv"
        with out_path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(gaps_pool[0].keys()))
            writer.writeheader()
            for g in gaps_pool:
                writer.writerow(g)
        print(f"CSV (live view, the real bug): {out_path} ({len(gaps_pool)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
