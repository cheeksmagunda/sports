"""Calibrate D87-D90 optimizer knobs against 2026 historical slates.

Pre-computes (samps, fields) once per slate, then sweeps OptimizeConfig
16 times per slate -- avoids repeated model loading, 5-7x faster.

Sweep space (16 combos, leverage=0 per synthesis):
  field_same_game_boost: 1.0 / 2.0 / 3.0 / 4.0
  field_same_team_boost: 1.0 / 2.0
  duplication_aware_payout: False / True

Usage:
  DATABASE_URL=$DATABASE_PUBLIC_URL uv run python scripts/calibrate_knobs.py
"""
from __future__ import annotations

import json
import os
import sys
from itertools import product
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("WNBA_ORACLE_MODEL_ARTIFACT_SHA",
                       "94f8e8606dab4d48652929bb3884fb9152e1abc766eeb2c2d86559f4318676cd")
os.environ.setdefault("PAYOUT_REGIME", "top_20")
os.environ.setdefault("OPTIMIZER_MAX_PER_TEAM", "2")
os.environ.setdefault("FIELD_MEASURED_OWNERSHIP_ENABLED", "true")

import structlog

structlog.configure(processors=[structlog.dev.ConsoleRenderer()])  # reduce noise

from wnba_oracle.picker.optimize import (  # noqa: E402
    DEFAULT_SLOT_MULTIPLIERS,
    OptimizeConfig,
    optimize_lineup,
)
from wnba_oracle.picker.payout import default_curve_for_regime  # noqa: E402
from wnba_oracle.scheduler.job2 import _build_specs  # noqa: E402

GRID = list(product(
    [1.0, 2.0, 3.0, 4.0],   # field_same_game_boost
    [1.0, 2.0],              # field_same_team_boost
    [False, True],           # duplication_aware_payout
))
CURVE = default_curve_for_regime("top_20")


def _score_lineup(player_ids, boost_by_pid, rs_by_pid) -> float:
    members = sorted(
        ((pid, rs_by_pid.get(int(pid), 0.0)) for pid in player_ids),
        key=lambda x: -x[1],
    )
    return sum(
        (DEFAULT_SLOT_MULTIPLIERS[i] + boost_by_pid.get(int(p), 0.0)) * rs
        for i, (p, rs) in enumerate(members)
    )


def main() -> int:
    from wnba_oracle.db.reads import read_leaderboards, read_slate_labels

    print("Loading slate data from DB...")
    sl = read_slate_labels()
    lb = read_leaderboards()

    slates_2026 = {d for d in sl["slate_date"].unique().to_list() if str(d).startswith("2026-")}
    lb_slates = set(lb["slate_date"].unique().to_list())
    valid_slates = sorted(slates_2026 & lb_slates)
    print(f"Found {len(valid_slates)} 2026 slates with both labels and leaderboard data\n")

    # ---- Phase 1: precompute specs once per slate -------------------------
    print("Phase 1: precomputing model predictions for each slate...")
    precomputed = {}
    for sd in valid_slates:
        slate = sl.filter(pl.col("slate_date") == sd)
        if slate.filter(pl.col("real_score").is_not_null()).height < 5:
            continue
        slate_lb = lb.filter(pl.col("slate_date") == sd)
        lb_scores = slate_lb["score"].to_list()
        if len(lb_scores) < 5:
            continue

        teams = slate["team_key"].unique().to_list()
        team_to_opp = {t: teams[(i + 1) % len(teams)] for i, t in enumerate(teams)}
        boost_by: dict[int, float] = {}
        rs_by: dict[int, float] = {}
        enrichment = []
        for r in slate.iter_rows(named=True):
            pid = int(r["platform_player_id"])
            boost = float(r["card_boost"])
            rs = float(r["real_score"]) if r["real_score"] is not None else 0.0
            boost_by[pid] = boost
            rs_by[pid] = rs
            enrichment.append({
                "real_sports_player_id": str(pid),
                "name": r["display_name"],
                "team": r["team_key"],
                "opponent": team_to_opp.get(r["team_key"], "UNK"),
                "position": "F",
                "card_boost": boost,
                "features_json": json.dumps({}),
            })

        samps, fields, _ = _build_specs(enrichment, slate_date=sd)
        if len(samps) < 5:
            continue

        precomputed[sd] = {
            "samps": samps,
            "fields": fields,
            "boost_by": boost_by,
            "rs_by": rs_by,
            "lb_scores": sorted(lb_scores, reverse=True),
        }
        print(f"  {sd}: {len(samps)} players, {len(lb_scores)} lb entries")

    slates = sorted(precomputed.keys())
    n = len(slates)
    print(f"\n{n} slates precomputed.\n")

    # ---- Phase 2: sweep parameters ----------------------------------------
    print("Phase 2: sweeping 16 parameter combos...")
    combo_results = []
    total = len(GRID) * n
    done = 0

    for game_boost, team_boost, dup_payout in GRID:
        label = f"game={game_boost:.0f}x team={team_boost:.0f}x dup={'Y' if dup_payout else 'N'}"
        slate_results = []
        for sd in slates:
            d = precomputed[sd]
            cfg = OptimizeConfig(
                top_n_filter=min(20, len(d["samps"])),
                n_samples=80,        # fast for sweep; validate winner at 400
                n_field_lineups=40,
                seed=2026,
                max_per_team=2,
                dynamic_team_cap=True,
                score_offset=2.0,
                leverage_weight=0.0,
                ceiling_weight=0.0,
                duplication_weight=0.0,
                field_same_game_boost=game_boost,
                field_same_team_boost=team_boost,
                duplication_aware_payout=dup_payout,
            )
            try:
                rec = optimize_lineup(d["samps"], d["fields"], CURVE, cfg=cfg)
            except Exception:
                done += 1
                continue

            our_score = _score_lineup(rec.player_ids, d["boost_by"], d["rs_by"])
            lb = d["lb_scores"]
            top1 = lb[0]
            top5 = lb[min(4, len(lb) - 1)]
            median = lb[min(9, len(lb) - 1)]

            slate_results.append({
                "beat_median": 1 if our_score > median else 0,
                "beat_top5": 1 if our_score > top5 else 0,
                "beat_top1": 1 if our_score >= top1 else 0,
                "gap": top1 - our_score,
                "our_score": our_score,
            })
            done += 1

        if done % (n // 2 or 1) == 0:
            pct = 100 * done / total
            print(f"  {done}/{total} ({pct:.0f}%)  last={label}")

        if not slate_results:
            continue
        combo_results.append({
            "label": label,
            "game_boost": game_boost,
            "team_boost": team_boost,
            "dup_payout": dup_payout,
            "n": len(slate_results),
            "beat_median_pct": 100 * np.mean([r["beat_median"] for r in slate_results]),
            "beat_top5_pct": 100 * np.mean([r["beat_top5"] for r in slate_results]),
            "beat_top1_pct": 100 * np.mean([r["beat_top1"] for r in slate_results]),
            "mean_gap": np.mean([r["gap"] for r in slate_results]),
        })

    print(f"\n{'=' * 80}")
    print(f"CALIBRATION RESULTS -- {n} slates, top-20 leaderboard benchmark")
    print(f"{'=' * 80}")
    combo_results.sort(key=lambda x: (-x["beat_median_pct"], -x["beat_top5_pct"]))
    print(f"  {'Config':28s} {'beat>=med':>9s} {'beat>=top5':>10s} {'beat>=top1':>10s} {'gap_vs_1st':>11s}")
    print(f"  {'-' * 28} {'-' * 9} {'-' * 10} {'-' * 10} {'-' * 11}")
    for r in combo_results:
        print(
            f"  {r['label']:28s} "
            f"{r['beat_median_pct']:>8.1f}%"
            f"{r['beat_top5_pct']:>9.1f}%"
            f"{r['beat_top1_pct']:>9.1f}%"
            f"{r['mean_gap']:>11.2f}"
        )

    best = combo_results[0]
    print(f"\n{'=' * 80}")
    print(f"WINNER: {best['label']}")
    print(f"  beat_median_pct  = {best['beat_median_pct']:.1f}%")
    print(f"  beat_top5_pct    = {best['beat_top5_pct']:.1f}%")
    print(f"  beat_top1_pct    = {best['beat_top1_pct']:.1f}%")
    print(f"  mean_gap_vs_top1 = {best['mean_gap']:.2f}")
    print("\nRecommended Railway env vars:")
    print(f"  FIELD_SAME_GAME_BOOST={best['game_boost']}")
    print(f"  FIELD_SAME_TEAM_BOOST={best['team_boost']}")
    print(f"  OPTIMIZER_DUPLICATION_AWARE_PAYOUT={'true' if best['dup_payout'] else 'false'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
