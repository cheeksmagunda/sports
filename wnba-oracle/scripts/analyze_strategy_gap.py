"""Strategy-gap analysis against the 2026 WNBA leaderboard + slate_labels corpus.

Answers two operator questions (2026-06-01):
  Q1. Dynamic stacking: do winning lineups stack 3+ on small slates, and how
      much does max_per_team=2 cost us there?
  Q2. Are we too contrarian: is the draft-popularity -> value relationship the
      NBA basketball-main port assumed (-0.457) actually present in WNBA 2026,
      and are winners playing chalk studs we fade?

Realized facts the corpus gives us (verified against lineup_json):
  - slate_labels.real_score is the REALIZED post-game real_score.
  - lineup score = real_score * multiplier; multiplier = slot_base + card_boost.
  - slot_base in {2.0, 1.8, 1.6, 1.4, 1.2}; user picks which player gets which.

Run: uv run python scripts/analyze_strategy_gap.py
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

SLOTS = np.array([2.0, 1.8, 1.6, 1.4, 1.2])


def load_corpus(year_prefix: str = "2026") -> tuple[pd.DataFrame, pd.DataFrame]:
    from wnba_oracle.db.reads import read_leaderboards, read_slate_labels

    sl = read_slate_labels().filter(pl.col("slate_date").str.starts_with(year_prefix)).to_pandas()
    lb = read_leaderboards().filter(pl.col("slate_date").str.starts_with(year_prefix)).to_pandas()
    return sl, lb


def best_lineup(pool: pd.DataFrame, max_per_team: int) -> tuple[float, list, int]:
    """Realized-oracle: pick 5 of `pool` maximizing sum(value*(slot+boost)) with
    optimal (rearrangement) slot assignment, subject to a per-team cap.

    Returns (score, chosen_rows, max_stack)."""
    vals = pool["real_score"].to_numpy(float)
    boosts = pool["card_boost"].to_numpy(float)
    teams = pool["team_key"].astype(str).to_numpy()
    n = len(pool)
    best_s, best_combo = -1.0, None
    for combo in itertools.combinations(range(n), 5):
        idx = list(combo)
        t = teams[idx]
        # team cap
        _, counts = np.unique(t, return_counts=True)
        if counts.max() > max_per_team:
            continue
        v = vals[idx]
        b = boosts[idx]
        order = np.argsort(v)[::-1]  # highest value -> highest slot
        s = float(np.sum(v[order] * (SLOTS + b[order])))
        if s > best_s:
            best_s, best_combo = s, idx
    if best_combo is None:
        # No lineup satisfies the cap (e.g. 1-game slate under max_per_team=2:
        # 5 players across 2 teams forces 3+ on one side by pigeonhole).
        return float("nan"), None, 0
    _, counts = np.unique(teams[best_combo], return_counts=True)
    return best_s, best_combo, int(counts.max())


def main() -> None:
    sl, lb = load_corpus("2026")
    slates = sorted(sl["slate_date"].unique())
    print(f"2026 corpus: {len(slates)} slates, {len(sl)} player-rows, {len(lb)} leaderboard rows\n")

    # ---- Per-slate setup ----
    games_by_slate, pool_by_slate = {}, {}
    for sd in slates:
        pool = sl[sl["slate_date"] == sd].drop_duplicates("platform_player_id").copy()
        pool_by_slate[sd] = pool
        games_by_slate[sd] = pool["team_key"].nunique() / 2.0

    # ================= Q1: STACKING =================
    print("=" * 78)
    print("Q1. STACKING IN WINNING LINEUPS, BY SLATE SIZE")
    print("=" * 78)
    rows = []
    for sd in slates:
        ng = games_by_slate[sd]
        lb_s = lb[lb["slate_date"] == sd].sort_values("rank")
        if lb_s.empty:
            continue
        for _, r in lb_s.iterrows():
            lj = (
                json.loads(r["lineup_json"])
                if isinstance(r["lineup_json"], str)
                else r["lineup_json"]
            )
            tids = [p.get("teamId") for p in lj]
            _, c = np.unique([t for t in tids if t is not None], return_counts=True)
            rows.append(
                {
                    "slate": sd,
                    "games": ng,
                    "rank": int(r["rank"]),
                    "score": float(r["score"]),
                    "max_stack": int(c.max()),
                }
            )
    d = pd.DataFrame(rows)
    d["game_bucket"] = pd.cut(
        d["games"], [0, 1.5, 2.5, 100], labels=["1 game", "2 games", "3+ games"]
    )

    print("\n-- Top-20 finishers: max same-team count by slate size --")
    for gb, grp in d.groupby("game_bucket", observed=True):
        share3 = (grp["max_stack"] >= 3).mean()
        print(
            f"  {gb:9s} (n={len(grp):4d} entries): mean max-stack={grp['max_stack'].mean():.2f}, "
            f"%lineups w/ 3+ from one team={share3:5.1%}, max seen={grp['max_stack'].max()}"
        )

    print("\n-- WINNERS ONLY (rank==1): max same-team count by slate size --")
    w = d[d["rank"] == 1]
    for gb, grp in w.groupby("game_bucket", observed=True):
        share3 = (grp["max_stack"] >= 3).mean()
        print(
            f"  {gb:9s} (n={len(grp):3d} winners): mean max-stack={grp['max_stack'].mean():.2f}, "
            f"%winners w/ 3+ from one team={share3:5.1%}"
        )

    print("\n-- Oracle (perfect-hindsight) lineup: cost of the max_per_team=2 cap --")
    print(
        f"  {'slate':12s} {'games':5s} {'oracle_cap2':>11s} {'oracle_nocap':>12s} "
        f"{'cap_cost':>9s} {'nocap_stack':>11s} {'winner':>7s}"
    )
    cap_cost_small, cap_cost_big = [], []
    for sd in slates:
        pool = pool_by_slate[sd]
        if len(pool) < 5:
            continue
        ng = games_by_slate[sd]
        s2, _, _ = best_lineup(pool, max_per_team=2)
        s5, _, stack5 = best_lineup(pool, max_per_team=5)
        win = d[(d["slate"] == sd) & (d["rank"] == 1)]["score"]
        win_s = float(win.iloc[0]) if len(win) else float("nan")
        infeasible = np.isnan(s2)
        cost = (s5 - s2) if not infeasible else s5  # full lineup forfeited
        (cap_cost_small if ng <= 2 else cap_cost_big).append(cost)
        cap2_disp = "INFEAS" if infeasible else f"{s2:.2f}"
        print(
            f"  {sd:12s} {ng:5.1f} {cap2_disp:>11s} {s5:12.2f} {cost:9.2f} {stack5:11d} {win_s:7.2f}"
        )
    print(
        f"\n  Mean oracle cap-cost on <=2 game slates: {np.mean(cap_cost_small):.2f} pts "
        f"(n={len(cap_cost_small)})"
    )
    print(
        f"  Mean oracle cap-cost on  3+ game slates: {np.mean(cap_cost_big):.2f} pts "
        f"(n={len(cap_cost_big)})"
    )

    # ================= Q2: CONTRARIAN =================
    print("\n" + "=" * 78)
    print("Q2. POPULARITY -> VALUE RELATIONSHIP (does the NBA -0.457 hold for WNBA 2026?)")
    print("=" * 78)
    allp = []
    for sd in slates:
        pool = pool_by_slate[sd].copy()
        pool = pool[pool["drafts"].notna()]
        if len(pool) < 6:
            continue
        # ceiling contribution = what stage-1 ranks by (value at top slot)
        pool["ceil_contrib"] = pool["real_score"] * (2.0 + pool["card_boost"])
        pool["draft_pct"] = pool["drafts"].rank(pct=True)
        pool["val_pct"] = pool["real_score"].rank(pct=True)
        allp.append(pool)
    P = pd.concat(allp, ignore_index=True)
    print(f"\n  Players with measured drafts: {len(P)} across {P['slate_date'].nunique()} slates")
    print(f"  corr(drafts, realized real_score)      = {P['drafts'].corr(P['real_score']):+.3f}")
    print(f"  corr(drafts, realized ceil_contrib)    = {P['drafts'].corr(P['ceil_contrib']):+.3f}")
    print(f"  corr(draft_pct, val_pct) within-slate  = {P['draft_pct'].corr(P['val_pct']):+.3f}")
    print("  (basketball-main NBA claim was -0.457; contrarian fade assumes strong NEGATIVE)")

    # most-drafted half vs least-drafted half total value
    hi = P[P["draft_pct"] >= 0.5]["real_score"]
    lo = P[P["draft_pct"] < 0.5]["real_score"]
    print(f"\n  Most-drafted 50%: mean real_score={hi.mean():.3f}  (NBA claim: LOW)")
    print(f"  Least-drafted 50%: mean real_score={lo.mean():.3f}  (NBA claim: ~24-26% HIGHER)")
    print(f"  least/most ratio = {lo.mean() / hi.mean():.3f}x  (NBA claim ~1.25x)")

    print("\n-- Are the HIGHEST realized scorers chalk or contrarian? --")
    print("  For each slate, take the 5 players with the best realized ceil_contrib")
    print("  ('the obvious wins'), report their median draft percentile (1.0=most drafted):")
    dp = []
    for _sd, grp in P.groupby("slate_date"):
        top5 = grp.nlargest(5, "ceil_contrib")
        dp.append(top5["draft_pct"].median())
    print(
        f"  median draft-pct of the 5 best plays: {np.median(dp):.2f} "
        f"(0.50=neutral, >0.5 means the best plays were MORE drafted than average)"
    )

    # winner roster popularity
    print("\n-- What draft percentile do actual WINNERS roster? --")
    wdp = []
    for sd in slates:
        pool = pool_by_slate[sd]
        if pool["drafts"].notna().sum() < 6:
            continue
        pool = pool[pool["drafts"].notna()].copy()
        pool["draft_pct"] = pool["drafts"].rank(pct=True)
        pct_map = dict(zip(pool["platform_player_id"], pool["draft_pct"]))
        lb_w = lb[(lb["slate_date"] == sd) & (lb["rank"] == 1)]
        if lb_w.empty:
            continue
        lj = lb_w.iloc[0]["lineup_json"]
        lj = json.loads(lj) if isinstance(lj, str) else lj
        pcs = [pct_map.get(p.get("playerId")) for p in lj]
        pcs = [x for x in pcs if x is not None]
        if pcs:
            wdp.append(np.mean(pcs))
    print(
        f"  Mean draft-pct of winners' rostered players: {np.mean(wdp):.2f} "
        f"(across {len(wdp)} winners; >0.5 means winners lean CHALK)"
    )

    print("\n-- The single best play each slate: how often is it a popular stud? --")
    n_chalk_best, n_total = 0, 0
    for _sd, grp in P.groupby("slate_date"):
        best = grp.nlargest(1, "ceil_contrib").iloc[0]
        n_total += 1
        if best["draft_pct"] >= 0.6:
            n_chalk_best += 1
    print(f"  best single play was in top-40% most-drafted on {n_chalk_best}/{n_total} slates")


if __name__ == "__main__":
    main()
