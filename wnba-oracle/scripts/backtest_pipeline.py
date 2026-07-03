"""Out-of-sample backtest of the full picker pipeline on the 16 2026
WNBA slates we have in corpus.

For each slate:
  1. Build a mock enrichment from slate_labels (the same card_boost
     values the live cron sees pre-game) but withhold real_score from
     the predictor (use only as scoring ground truth).
  2. Run the full job2 pipeline: _build_specs -> optimize_lineup.
  3. Score the resulting lineup using REALIZED real_scores under the
     true game scoring formula: sum (slot_mult + card_boost) * real_score.
  4. Compare to the actual leaderboard: our score vs top-1 / top-5 /
     top-20 / median.

Caveats:
- The current trained EB artifact saw all 121 slates including these
  16 (mild data leakage). Reading the placement numbers with that in
  mind — they're an optimistic upper bound. A proper walk-forward
  retrains EB on slates < N for each test slate N; left for follow-up.
- features_json is empty (no Vegas / RotoWire signal in historical
  parquet), so game_script_multiplier degrades to 1.0x for every player.
  Live fire will have these signals — expect slight differentiation
  beyond what this backtest shows.
- max_per_team=2 + cohort=F-only matches prod settings.

Outputs a per-slate table + aggregate stats.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Match production env exactly
os.environ.setdefault("WNBA_ORACLE_MODEL_ARTIFACT_SHA",
                       "db18f6c9f495555e9df8f995e17679b93a7d26b1de77b39546d51ce2f5538f62")
os.environ.setdefault("CONTRARIAN_STRENGTH", "0.3")
os.environ.setdefault("CONTRARIAN_ENABLED", "true")
os.environ.setdefault("OPTIMIZER_MAX_PER_TEAM", "2")
os.environ.setdefault("PAYOUT_REGIME", "top_20")

from wnba_oracle.picker.optimize import (
    DEFAULT_SLOT_MULTIPLIERS,
    OptimizeConfig,
    optimize_lineup,
)
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.scheduler.job2 import _build_specs


def score_lineup_against_truth(
    player_ids: tuple[int, ...],
    boost_by_pid: dict[int, float],
    real_score_by_pid: dict[int, float],
    slot_multipliers: tuple[float, ...] = tuple(DEFAULT_SLOT_MULTIPLIERS),
) -> float:
    """The lineup score the platform would award post-tip.
    Rearranges by REALIZED real_score per the platform's auto-assignment."""
    members = [(pid, real_score_by_pid.get(int(pid), 0.0)) for pid in player_ids]
    # By rearrangement, highest realized value -> highest slot
    members.sort(key=lambda x: -x[1])
    total = 0.0
    for slot_idx, (pid, rs) in enumerate(members):
        boost = boost_by_pid.get(int(pid), 0.0)
        total += (slot_multipliers[slot_idx] + boost) * rs
    return total


def main() -> int:
    from wnba_oracle.db.reads import read_leaderboards, read_slate_labels

    sl = read_slate_labels()
    lb = read_leaderboards()
    test_slates = sorted(
        [d for d in sl["slate_date"].unique().to_list() if d.startswith("2026-")]
    )
    print(f"Backtesting on {len(test_slates)} 2026 slates")
    print(f"Using artifact SHA: {os.environ['WNBA_ORACLE_MODEL_ARTIFACT_SHA'][:16]}...")
    print()

    rows = []
    for sd in test_slates:
        slate = sl.filter(pl.col("slate_date") == sd)
        slate_lb = lb.filter(pl.col("slate_date") == sd).sort("rank")
        teams = slate["team_key"].unique().to_list()
        team_to_opp = {t: teams[(i + 1) % len(teams)] for i, t in enumerate(teams)}

        enrichment = []
        boost_by_pid: dict[int, float] = {}
        rs_by_pid: dict[int, float] = {}
        for r in slate.iter_rows(named=True):
            pid = int(r["platform_player_id"])
            boost = float(r["card_boost"])
            rs = float(r["real_score"]) if r["real_score"] is not None else 0.0
            boost_by_pid[pid] = boost
            rs_by_pid[pid] = rs
            enrichment.append({
                "real_sports_player_id": str(pid),
                "name": r["display_name"],
                "team": r["team_key"],
                "opponent": team_to_opp.get(r["team_key"], "UNK"),
                "position": "F",
                "card_boost": boost,
                "features_json": json.dumps({}),
            })

        # Run the same pipeline cron-job2 runs
        samps, fields, _projection_by_pid = _build_specs(enrichment, slate_date=sd)
        if len(samps) < 5:
            print(f"  {sd}  pool too small ({len(samps)}); skip")
            continue
        cfg = OptimizeConfig(
            top_n_filter=min(20, len(samps)),
            n_samples=300,
            n_field_lineups=50,
            seed=2026,
        )
        rec = optimize_lineup(samps, fields, default_curve_for_regime("top_20"), cfg=cfg)
        our_score = score_lineup_against_truth(rec.player_ids, boost_by_pid, rs_by_pid)

        # Leaderboard scores
        actual_top1 = float(slate_lb.row(0, named=True)["score"]) if slate_lb.height else 0.0
        actual_top5 = (
            float(slate_lb.filter(pl.col("rank") <= 5)["score"].min())
            if slate_lb.height >= 5 else 0.0
        )
        actual_top20 = (
            float(slate_lb["score"].min()) if slate_lb.height else 0.0
        )
        actual_median = (
            float(slate_lb["score"].median()) if slate_lb.height else 0.0
        )

        # Where would we have placed?
        all_scores = sorted(slate_lb["score"].to_list(), reverse=True)
        placement = sum(1 for s in all_scores if s >= our_score) + 1

        # Which players did we pick? Which did winners pick?
        our_pids = {int(p) for p in rec.player_ids}
        win_pids = set()
        if slate_lb.height:
            win_lineup = json.loads(slate_lb.row(0, named=True)["lineup_json"])
            win_pids = {int(p["playerId"]) for p in win_lineup}
        overlap = len(our_pids & win_pids)

        rows.append({
            "slate_date": sd,
            "our_score": round(our_score, 2),
            "top1": round(actual_top1, 2),
            "top5": round(actual_top5, 2),
            "top20": round(actual_top20, 2),
            "median": round(actual_median, 2),
            "placement": placement,
            "overlap_with_winner": overlap,
            "n_pool": len(samps),
        })

    df = pl.DataFrame(rows)
    print()
    print("Per-slate results:")
    with pl.Config(tbl_rows=20, tbl_cols=10, tbl_width_chars=140):
        print(df)

    print()
    print("=== Aggregate ===")
    print(f"Slates: {len(rows)}")
    n_top20 = sum(1 for r in rows if r["placement"] <= 20)
    n_top5 = sum(1 for r in rows if r["placement"] <= 5)
    n_top1 = sum(1 for r in rows if r["placement"] == 1)
    print(f"Top-20 finishes: {n_top20}/{len(rows)} ({100*n_top20/len(rows):.0f}%)")
    print(f"Top-5  finishes: {n_top5}/{len(rows)} ({100*n_top5/len(rows):.0f}%)")
    print(f"Top-1  finishes: {n_top1}/{len(rows)} ({100*n_top1/len(rows):.0f}%)")
    print(f"Median placement: {int(np.median([r['placement'] for r in rows]))}")
    print(f"Mean score gap vs top-1: {np.mean([r['top1'] - r['our_score'] for r in rows]):.2f}")
    print(f"Mean overlap with winner: {np.mean([r['overlap_with_winner'] for r in rows]):.2f}/5")
    return 0


if __name__ == "__main__":
    sys.exit(main())
