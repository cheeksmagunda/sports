"""Where is the edge? Two questions, full 121-slate corpus, no new data needed.

Q1. Is card_boost systematically miscalibrated? If `boost x E[real]` is truly
    equalized (the platform's goal), there is no boost-level edge and the game
    is variance. If high-boost lottery tickets systematically UNDER-produce
    their handicap (or low-boost studs OVER-produce on a floor basis), we can
    exploit it slate-independently.

Q2. What boost level do actual contest WINNERS roster vs the pool? If winners
    skew low-boost (studs), our `pred x (2+boost)` ceiling ranking is backwards.

Also reports the floor/ceiling shape per boost bucket (P(real>=3) etc.), since
WNBA real_score is tight (max ~10) and floor may beat ceiling here.
"""
from __future__ import annotations

import json

import numpy as np
import polars as pl

SLOTS = [2.0, 1.8, 1.6, 1.4, 1.2]


def boost_prior(b: float) -> float:
    return max(0.5, 3.16 - 0.45 * b)


def main() -> None:
    sl = pl.read_parquet("data/historical/slate_labels/**/data.parquet")
    lb = pl.read_parquet("data/historical/leaderboards/**/data.parquet")

    df = sl.select(["slate_date", "platform_player_id", "card_boost", "real_score", "drafts"]).filter(
        pl.col("real_score").is_not_null()
    ).to_pandas()
    df["bucket"] = np.minimum((df["card_boost"] / 0.5).astype(int) * 0.5, 3.0)
    df["ceil_contrib"] = df["real_score"] * (2.0 + df["card_boost"])
    df["prior"] = df["card_boost"].map(boost_prior)
    df["resid"] = df["real_score"] - df["prior"]

    print("=" * 80)
    print("Q1. BOOST CALIBRATION  (is boost x E[real] really equalized?)")
    print("=" * 80)
    print(f"{'boost':>6} {'n':>5} {'mean_real':>9} {'prior':>6} {'resid':>6} "
          f"{'P(real>=3)':>10} {'P(real>=4)':>10} {'mean_ceilContrib':>16}")
    for b, g in df.groupby("bucket"):
        print(f"{b:>6.1f} {len(g):>5} {g['real_score'].mean():>9.2f} {g['prior'].mean():>6.2f} "
              f"{g['resid'].mean():>+6.2f} {(g['real_score']>=3).mean():>10.2f} "
              f"{(g['real_score']>=4).mean():>10.2f} {g['ceil_contrib'].mean():>16.2f}")
    print("\n  resid = realized - boost_prior. If ~0 across buckets, the boost MEAN is")
    print("  well-calibrated. ceil_contrib = real*(2+boost) is what our ranker maximizes.")

    # Q2: winner boost profile from leaderboards
    print("\n" + "=" * 80)
    print("Q2. WHAT BOOST DO WINNERS ROSTER? (multiplierBonus in lineup_json)")
    print("=" * 80)
    rows = []
    for r in lb.iter_rows(named=True):
        lj = json.loads(r["lineup_json"]) if isinstance(r["lineup_json"], str) else r["lineup_json"]
        boosts = [float(p.get("multiplierBonus", 0.0)) for p in lj]
        reals = [float(p.get("value", 0.0)) for p in lj]
        rows.append({"slate": r["slate_date"], "rank": int(r["rank"]),
                     "mean_boost": float(np.mean(boosts)), "mean_real": float(np.mean(reals))})
    L = pl.DataFrame(rows).to_pandas()
    pool_mean = float(df["card_boost"].mean())
    print(f"  pool mean boost (all available players): {pool_mean:.2f}")
    for lo, hi, lab in [(1, 1, "rank 1 (winners)"), (1, 3, "top 3"), (1, 20, "top 20")]:
        sub = L[(L["rank"] >= lo) & (L["rank"] <= hi)]
        print(f"  {lab:18s}: mean rostered boost {sub['mean_boost'].mean():.2f}  "
              f"mean rostered real {sub['mean_real'].mean():.2f}")
    print("\n  If winners' rostered boost < pool mean, they fade the high-boost lottery")
    print("  tickets our ceiling ranker loves and play lower-boost, higher-floor studs.")

    # Q3: the realized best-5 per slate -- boost profile + how our ranker sees them
    print("\n" + "=" * 80)
    print("Q3. THE ACTUALLY-BEST PLAYS (top-5 realized ceil_contrib / slate)")
    print("=" * 80)
    best_boost, best_real = [], []
    for _sd, g in df.groupby("slate_date"):
        top5 = g.nlargest(5, "ceil_contrib")
        best_boost.append(top5["card_boost"].mean())
        best_real.append(top5["real_score"].mean())
    print(f"  best-5 mean boost: {np.mean(best_boost):.2f} (vs pool {pool_mean:.2f})")
    print(f"  best-5 mean real:  {np.mean(best_real):.2f} (vs pool {df['real_score'].mean():.2f})")
    # Correlation within slate: does higher boost -> higher realized ceil_contrib?
    cors = []
    for _sd, g in df.groupby("slate_date"):
        if len(g) >= 8:
            cors.append(np.corrcoef(g["card_boost"], g["ceil_contrib"])[0, 1])
    print(f"  within-slate corr(boost, realized ceil_contrib): {np.nanmean(cors):+.3f}")
    print("  (our ranker assumes this is strongly POSITIVE; if it's ~0 or negative,")
    print("   ranking by (2+boost) is chasing a ceiling that doesn't pay off.)")


if __name__ == "__main__":
    main()
