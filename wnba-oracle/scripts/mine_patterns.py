"""Mine the 121-slate leaderboard corpus for winning patterns we may
have missed. NOT for overfitting — surfaces aggregate statistics with
sample sizes so the reader can judge significance.

Sections:
  A. Card-boost-sum distribution by finishing rank tier.
  B. Slate-top-K hit rate by tier (do winners always have THE top
     scorer, or how often can you win without them).
  C. Multiplier-pattern shape: which slots get the high-boost cards?
  D. Anchor + leverage: how many of the 5 picks are at the TWO
     extreme boost tiers (high anchor + low leverage)?
  E. Repeat winners: same user_id winning multiple slates?
  F. 2025 vs 2026 drift: is the meta the same?

No predictions, just describing what worked.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def explode_lineups(lb: pl.DataFrame) -> pl.DataFrame:
    """One row per (slate_date, entry_id, slot)."""
    rows = []
    for r in lb.iter_rows(named=True):
        for slot_idx, p in enumerate(json.loads(r["lineup_json"])):
            rows.append({
                "slate_date": r["slate_date"],
                "entry_id": r["entry_id"],
                "rank": r["rank"],
                "user_id": r["user_id"],
                "entry_score": r["score"],
                "slot": slot_idx,
                "player_id": int(p["playerId"]),
                "display_name": p.get("displayName", ""),
                "team_id": p.get("teamId"),
                "multiplier": float(p["multiplier"]),
                "multiplier_bonus": float(p.get("multiplierBonus", 0.0)),
                "value": float(p.get("value", 0.0) or 0.0),
                "player_score": float(p.get("score", 0.0) or 0.0),
            })
    return pl.DataFrame(rows)


def main() -> int:
    from wnba_oracle.db.reads import read_leaderboards, read_slate_labels

    lb = read_leaderboards()
    sl = read_slate_labels()
    pp = explode_lineups(lb)
    pp = pp.with_columns(
        pl.when(pl.col("rank") == 1).then(pl.lit("winner"))
          .when(pl.col("rank") <= 5).then(pl.lit("top5"))
          .otherwise(pl.lit("rest")).alias("tier")
    )
    print(f"Corpus: {lb.height} entries across {lb['slate_date'].n_unique()} slates")

    # A. Card-boost-sum distribution by tier
    section("A. Sum of card_boost across 5 picks, by finishing tier")
    boost_per_entry = (
        pp.group_by(["slate_date", "entry_id"])
        .agg([
            pl.col("rank").first().alias("rank"),
            pl.col("multiplier_bonus").sum().alias("boost_sum"),
        ])
        .with_columns(
            pl.when(pl.col("rank") == 1).then(pl.lit("winner"))
              .when(pl.col("rank") <= 5).then(pl.lit("top5"))
              .otherwise(pl.lit("rest")).alias("tier")
        )
    )
    by_tier = (
        boost_per_entry.group_by("tier")
        .agg([
            pl.col("boost_sum").mean().round(2).alias("mean_boost_sum"),
            pl.col("boost_sum").median().round(2).alias("median"),
            pl.col("boost_sum").quantile(0.1).round(2).alias("p10"),
            pl.col("boost_sum").quantile(0.9).round(2).alias("p90"),
            pl.len().alias("n"),
        ])
        .sort("tier")
    )
    print(by_tier)
    print("Reading: 'mean_boost_sum' is the sum of 5 card_boost values. Max possible ~15, typical ~6.")

    # B. Slate-top-K hit rate
    section("B. Did winners pick the slate's top realized scorers?")
    slate_top = (
        pp.group_by(["slate_date", "player_id"])
        .agg(pl.col("value").max().alias("realized_value"))
        .sort(["slate_date", "realized_value"], descending=[False, True])
    )
    # Per slate, top-3 player_ids
    slate_top3 = (
        slate_top.group_by("slate_date")
        .agg(pl.col("player_id").head(3).alias("top3_pids"))
    )
    pp_with_top = pp.join(slate_top3, on="slate_date")
    per_entry_hit = (
        pp_with_top.group_by(["slate_date", "entry_id"])
        .agg([
            pl.col("rank").first().alias("rank"),
            pl.col("player_id").alias("picks"),
            pl.col("top3_pids").first().alias("top3"),
        ])
    )
    hit_counts = []
    for r in per_entry_hit.iter_rows(named=True):
        picks = set(r["picks"])
        top3 = set(r["top3"])
        hit_counts.append({"rank": r["rank"], "hit_top1": int(list(top3)[0] in picks if r["top3"] else False),
                            "n_top3_in_lineup": len(picks & top3)})
    hc = pl.DataFrame(hit_counts).with_columns(
        pl.when(pl.col("rank") == 1).then(pl.lit("winner"))
          .when(pl.col("rank") <= 5).then(pl.lit("top5"))
          .otherwise(pl.lit("rest")).alias("tier")
    )
    print(hc.group_by("tier").agg([
        pl.col("n_top3_in_lineup").mean().round(2).alias("mean_top3_picks"),
        (pl.col("n_top3_in_lineup") == 0).sum().alias("n_zero_top3"),
        pl.len().alias("n"),
    ]).sort("tier"))
    print("Reading: avg # of slate's top-3 realized scorers in lineup, by tier.")

    # C. Where does the highest-boost card go? Slot distribution.
    section("C. Slot allocation of the highest-boost card per lineup")
    rows = []
    for (sd, eid), grp in pp.group_by(["slate_date", "entry_id"]):
        gl = list(grp.iter_rows(named=True))
        max_boost = max(gl, key=lambda r: r["multiplier_bonus"])
        rank = gl[0]["rank"]
        rows.append({
            "rank": rank,
            "slot_of_max_boost": max_boost["slot"],  # 0=highest slot (2.0x), 4=lowest (1.2x)
            "boost": max_boost["multiplier_bonus"],
        })
    sdf = pl.DataFrame(rows).with_columns(
        pl.when(pl.col("rank") == 1).then(pl.lit("winner"))
          .when(pl.col("rank") <= 5).then(pl.lit("top5"))
          .otherwise(pl.lit("rest")).alias("tier")
    )
    print(sdf.group_by(["tier", "slot_of_max_boost"]).agg(pl.len().alias("n")).sort(["tier", "slot_of_max_boost"]))
    print("Reading: where does the highest-boost card land? slot 0 = highest payoff slot (2.0x); slot 4 = lowest (1.2x).")

    # D. Anchor vs leverage composition
    section("D. Anchor (low-boost) vs leverage (high-boost) ratio in winning lineups")
    boost_tiers_per_entry = []
    for (sd, eid), grp in pp.group_by(["slate_date", "entry_id"]):
        gl = list(grp.iter_rows(named=True))
        boosts = [r["multiplier_bonus"] for r in gl]
        boost_tiers_per_entry.append({
            "rank": gl[0]["rank"],
            "n_anchor_low_boost": sum(1 for b in boosts if b < 1.0),
            "n_leverage_high_boost": sum(1 for b in boosts if b >= 2.0),
            "n_mid": sum(1 for b in boosts if 1.0 <= b < 2.0),
        })
    bdf = pl.DataFrame(boost_tiers_per_entry).with_columns(
        pl.when(pl.col("rank") == 1).then(pl.lit("winner"))
          .when(pl.col("rank") <= 5).then(pl.lit("top5"))
          .otherwise(pl.lit("rest")).alias("tier")
    )
    print(bdf.group_by("tier").agg([
        pl.col("n_anchor_low_boost").mean().round(2).alias("avg_anchor_<1.0"),
        pl.col("n_mid").mean().round(2).alias("avg_mid_1-2"),
        pl.col("n_leverage_high_boost").mean().round(2).alias("avg_leverage_>=2.0"),
        pl.len().alias("n"),
    ]).sort("tier"))
    print("Reading: avg # of cards per lineup in each boost tier, by finishing tier.")

    # E. Repeat winners
    section("E. Repeat winners across the corpus")
    rep = (
        lb.filter(pl.col("rank") == 1)
        .group_by("user_id")
        .agg(pl.len().alias("n_wins"))
        .sort("n_wins", descending=True)
        .head(8)
    )
    print(rep)

    # F. 2025 vs 2026 drift in winners' boost composition
    section("F. Mean winner card_boost sum: 2025 vs 2026")
    winners = boost_per_entry.filter(pl.col("rank") == 1).with_columns(
        pl.col("slate_date").str.slice(0, 4).alias("season")
    )
    print(winners.group_by("season").agg([
        pl.col("boost_sum").mean().round(2).alias("mean"),
        pl.col("boost_sum").median().round(2).alias("median"),
        pl.len().alias("n_winners"),
    ]).sort("season"))
    print("If the means differ much, 2025 patterns may not transfer to 2026.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
