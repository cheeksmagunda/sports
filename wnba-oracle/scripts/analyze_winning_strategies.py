"""Strategy analysis on the 16-slate WNBA leaderboards corpus.

Goal: pull patterns from how top-20 finishers built winning lineups
across 2026-05-08..2026-05-25, that generalize to future slates.

Not overfitting: small-n (16 slates, 320 lineups). Report ranges +
sample dispersion, not single numbers. Compare top-1 vs top-5 vs top-20
to separate signal from noise.

Outputs to stdout. Inputs: data/historical/{leaderboards,slate_labels}/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def load():
    from wnba_oracle.db.reads import read_leaderboards, read_slate_labels

    lb = read_leaderboards()
    sl = read_slate_labels()
    # Explode lineup_json into per-player rows for easier analysis.
    expanded_rows = []
    for row in lb.iter_rows(named=True):
        lineup = json.loads(row["lineup_json"])
        for slot_idx, p in enumerate(lineup):
            expanded_rows.append({
                "slate_date": row["slate_date"],
                "contest_id": row["contest_id"],
                "entry_id": row["entry_id"],
                "rank": row["rank"],
                "user_id": row["user_id"],
                "total_score": row["score"],
                "slot": slot_idx,
                "player_id": int(p["playerId"]),
                "display_name": p.get("displayName", ""),
                "team_id": p.get("teamId"),
                "multiplier": float(p["multiplier"]),
                "multiplier_bonus": float(p.get("multiplierBonus", 0.0)),
                "value": float(p["value"]),
                "player_score": float(p["score"]),
                "real_rank": p.get("realRank"),
            })
    per_player = pl.DataFrame(expanded_rows)
    return lb, sl, per_player


def section(title: str):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def main():
    lb, _sl, pp = load()
    n_slates = lb["slate_date"].n_unique()
    print(f"Corpus: {n_slates} slates, {lb.height} entries, {pp.height} player-slots")
    print(f"Slate range: {lb['slate_date'].min()} .. {lb['slate_date'].max()}")

    # --- 0. Tie density: how often do entries share a rank? ---
    section("0. Tie density — small player pool produces score ties")
    rank_size = (
        lb.group_by(["slate_date", "rank"])
        .agg(pl.len().alias("n_entries_at_rank"))
    )
    print("Per-slate, how often did multiple entries share a rank in top-20?")
    by_slate_ties = (
        rank_size.group_by("slate_date")
        .agg([
            (pl.col("n_entries_at_rank") > 1).sum().alias("n_tied_ranks"),
            pl.col("n_entries_at_rank").max().alias("max_tied_at_one_rank"),
        ])
        .sort("slate_date")
    )
    print(by_slate_ties)
    print()
    print("Reading: 'max_tied_at_one_rank' = N means N players in top-20 tied for the same rank.")
    print("Larger N => smaller effective lineup space => the contest converges on a small set of 'optimal' lineups.")

    # --- 1. Multiplier budget: do top finishers use the same total? ---
    section("1. Multiplier budget — is there an implied constraint?")
    per_entry_mult = (
        pp.group_by(["slate_date", "entry_id"])
        .agg([
            pl.col("rank").first().alias("rank"),
            pl.col("multiplier").sum().round(2).alias("total_mult"),
        ])
        .sort(["slate_date", "rank"])
    )
    by_rank = (
        per_entry_mult.with_columns(
            pl.when(pl.col("rank") == 1).then(pl.lit("winner"))
              .when(pl.col("rank") <= 5).then(pl.lit("top5"))
              .otherwise(pl.lit("rest")).alias("tier"),
        )
        .group_by("tier")
        .agg([
            pl.col("total_mult").mean().round(2).alias("mean_total"),
            pl.col("total_mult").std().round(2).alias("std_total"),
            pl.col("total_mult").min().alias("min_total"),
            pl.col("total_mult").max().alias("max_total"),
            pl.len().alias("n_entries"),
        ])
        .sort("tier")
    )
    print("Sum of 5 chosen multipliers per entry, aggregated by finishing rank:")
    print(by_rank)
    overall = per_entry_mult["total_mult"]
    print(f"\nOverall p10/p50/p90: {overall.quantile(0.1):.2f} / {overall.quantile(0.5):.2f} / {overall.quantile(0.9):.2f}")
    print("Most common bucket: round to nearest 0.5 ->")
    bucketed = (per_entry_mult["total_mult"] / 0.5).round(0) * 0.5
    print(bucketed.value_counts().sort("count", descending=True).head(5))

    # --- 2. Max-multiplier concentration ---
    section("2. Multiplier concentration — top picks vs spread")
    max_mult = (
        pp.group_by(["slate_date", "entry_id"])
        .agg([
            pl.col("rank").first().alias("rank"),
            pl.col("multiplier").max().alias("max_mult"),
            pl.col("multiplier").min().alias("min_mult"),
        ])
    )
    by_rank2 = (
        max_mult.with_columns(
            pl.when(pl.col("rank") == 1).then(pl.lit("winner"))
              .when(pl.col("rank") <= 5).then(pl.lit("top5"))
              .otherwise(pl.lit("rest")).alias("tier"),
        )
        .group_by("tier")
        .agg([
            pl.col("max_mult").mean().round(2).alias("mean_max"),
            pl.col("min_mult").mean().round(2).alias("mean_min"),
            (pl.col("max_mult") - pl.col("min_mult")).mean().round(2).alias("mean_spread"),
            pl.len().alias("n_entries"),
        ])
        .sort("tier")
    )
    print("Per-tier mean of (max mult), (min mult), (spread max-min):")
    print(by_rank2)

    # --- 3. Where does the max multiplier go? Sorted by realized value rank ---
    section("3. Does the max multiplier land on the top scorer?")
    # For each entry, find which slot held the max multiplier, and what was the realized rank of that player on the slate.
    # We'll classify: did the player with max-mult also have one of the top-2 values in the lineup?
    entry_slot_summary = []
    for _grp_keys, grp in pp.group_by(["slate_date", "entry_id"]):
        rows = list(grp.iter_rows(named=True))
        entry_rank = rows[0]["rank"]
        max_mult_player = max(rows, key=lambda r: r["multiplier"])
        sorted_by_val = sorted(rows, key=lambda r: -r["value"])
        value_rank_of_max_mult = next(
            i + 1 for i, r in enumerate(sorted_by_val)
            if r["player_id"] == max_mult_player["player_id"]
        )
        entry_slot_summary.append({
            "rank": int(entry_rank),
            "max_mult": max_mult_player["multiplier"],
            "max_mult_player_value_rank": value_rank_of_max_mult,
        })
    es = pl.DataFrame(entry_slot_summary)
    crosstab = (
        es.with_columns([
            (pl.col("max_mult_player_value_rank") <= 2).alias("smart_pick"),
            pl.when(pl.col("rank") == 1).then(pl.lit("winner"))
              .when(pl.col("rank") <= 5).then(pl.lit("top5"))
              .otherwise(pl.lit("rest")).alias("tier"),
        ])
        .group_by("tier")
        .agg([
            (pl.col("smart_pick").sum() / pl.len()).round(3).alias("pct_max_mult_in_top2_value"),
            pl.len().alias("n"),
        ])
        .sort("tier")
    )
    print("Of the player with the max multiplier in each lineup, what % land")
    print("in the top-2 realized values? (i.e. high mult on actually-best player)")
    print(crosstab)

    # --- 4. Player ownership across top-20 (proxy for what worked) ---
    section("4. Player ownership in top-20: which players show up most?")
    # Count how many of the 20 entries per slate include each player
    own = (
        pp.group_by(["slate_date", "player_id", "display_name"])
        .agg(pl.col("entry_id").n_unique().alias("n_owned"))
    )
    # Per-slate ownership distribution: how concentrated are top-20 lineups?
    by_slate = own.group_by("slate_date").agg([
        pl.col("n_owned").max().alias("max_owned_by_one_player"),
        (pl.col("n_owned") >= 15).sum().alias("n_consensus_15plus"),
        (pl.col("n_owned") >= 10).sum().alias("n_consensus_10plus"),
        (pl.col("n_owned") >= 5).sum().alias("n_consensus_5plus"),
        pl.col("player_id").n_unique().alias("n_distinct_players"),
    ]).sort("slate_date")
    print("Per slate: how many distinct players appeared in top-20 lineups?")
    print("(out of 20 entries × 5 slots = 100 player-slots per slate)")
    print(by_slate)
    print()
    print("Read: when 'n_consensus_15plus' = 1, exactly one player was on 15+/20 winning lineups (a near-mandatory chalk pick).")

    # --- 5. Multiplier given to high-ownership ("chalk") players ---
    section("5. Do winners boost chalk or fade chalk?")
    # Merge per-player ownership rate (within top-20) onto each pp row
    own_for_join = own.with_columns([
        pl.col("n_owned").alias("times_owned_top20"),
    ])
    pp_with_own = pp.join(own_for_join.select(["slate_date", "player_id", "times_owned_top20"]),
                          on=["slate_date", "player_id"], how="left")
    pp_with_own = pp_with_own.with_columns([
        pl.when(pl.col("times_owned_top20") >= 15).then(pl.lit("chalk(15+)"))
          .when(pl.col("times_owned_top20") >= 8).then(pl.lit("mid(8-14)"))
          .when(pl.col("times_owned_top20") >= 3).then(pl.lit("contrarian(3-7)"))
          .otherwise(pl.lit("unique(1-2)")).alias("own_tier"),
        pl.when(pl.col("rank") == 1).then(pl.lit("winner"))
          .when(pl.col("rank") <= 5).then(pl.lit("top5"))
          .otherwise(pl.lit("rest")).alias("finish_tier"),
    ])
    mult_by_tier = (
        pp_with_own.group_by(["finish_tier", "own_tier"])
        .agg([
            pl.col("multiplier").mean().round(2).alias("mean_mult"),
            pl.col("multiplier").max().round(2).alias("max_mult_seen"),
            pl.len().alias("n_slots"),
        ])
        .sort(["finish_tier", "own_tier"])
    )
    print("Mean chosen multiplier, broken out by finish tier × ownership tier:")
    print(mult_by_tier)

    # --- 6. Team stacking ---
    section("6. Team diversification — how many teams per lineup?")
    team_count = (
        pp.group_by(["slate_date", "entry_id"])
        .agg([
            pl.col("rank").first().alias("rank"),
            pl.col("team_id").n_unique().alias("n_teams"),
        ])
    )
    print("Distribution of distinct teams per 5-player lineup:")
    print(team_count["n_teams"].value_counts().sort("n_teams"))
    by_finish = (
        team_count.with_columns(
            pl.when(pl.col("rank") == 1).then(pl.lit("winner"))
              .when(pl.col("rank") <= 5).then(pl.lit("top5"))
              .otherwise(pl.lit("rest")).alias("tier"),
        )
        .group_by("tier")
        .agg(pl.col("n_teams").mean().round(2).alias("mean_n_teams"))
        .sort("tier")
    )
    print(by_finish)

    # --- 7. How often does the top scorer of the day appear in winning lineups? ---
    section("7. Did winners hit the actual slate-top scorer?")
    # For each slate, the highest-value player is the player with the max
    # `value` observed across any lineup's slot for that slate.
    slate_top_player = (
        pp.group_by(["slate_date", "player_id", "display_name"])
        .agg(pl.col("value").max().alias("realized_value"))
        .sort(["slate_date", "realized_value"], descending=[False, True])
    )
    slate_top1 = (
        slate_top_player.group_by("slate_date")
        .agg([
            pl.col("player_id").first().alias("top1_pid"),
            pl.col("display_name").first().alias("top1_name"),
            pl.col("realized_value").first().alias("top1_value"),
        ])
    )
    # Did each entry's lineup include the top1 player?
    pp_top1 = pp.join(slate_top1, on="slate_date").with_columns(
        (pl.col("player_id") == pl.col("top1_pid")).alias("has_top1")
    )
    has_top1_by_entry = pp_top1.group_by(["slate_date", "entry_id"]).agg([
        pl.col("rank").first().alias("rank"),
        pl.col("has_top1").any().alias("included_slate_top1"),
    ])
    pct = (
        has_top1_by_entry.with_columns(
            pl.when(pl.col("rank") == 1).then(pl.lit("winner"))
              .when(pl.col("rank") <= 5).then(pl.lit("top5"))
              .otherwise(pl.lit("rest")).alias("tier"),
        )
        .group_by("tier")
        .agg([
            (pl.col("included_slate_top1").sum() / pl.len()).round(3).alias("pct_with_slate_top1"),
            pl.len().alias("n"),
        ])
        .sort("tier")
    )
    print("Of top-20 entries, % that included the slate's actual top scorer:")
    print(pct)
    print()
    print("Per-slate detail (winner only):")
    winner_top1 = has_top1_by_entry.filter(pl.col("rank") == 1).join(slate_top1, on="slate_date").select([
        "slate_date", "top1_name", "top1_value", "included_slate_top1",
    ])
    print(winner_top1)

    # --- 8. The multiplier on the slate-top scorer (when winner included them) ---
    section("8. When winner had the slate's top scorer, what multiplier did they use?")
    winner_slots = pp.filter(pl.col("rank") == 1).join(slate_top1, on="slate_date")
    winner_top1_slot = winner_slots.filter(pl.col("player_id") == pl.col("top1_pid"))
    if winner_top1_slot.height:
        print(winner_top1_slot.select([
            "slate_date", "top1_name", "multiplier", "value", "player_score",
        ]).sort("slate_date"))
        print(f"\nMean multiplier on slate-top scorer (winners): {winner_top1_slot['multiplier'].mean():.2f}")
        print(f"Median: {winner_top1_slot['multiplier'].median():.2f}")
    else:
        print("(no winner had the slate top scorer)")

    print()
    print("=" * 78)
    print("END OF ANALYSIS")


if __name__ == "__main__":
    sys.exit(main() or 0)
