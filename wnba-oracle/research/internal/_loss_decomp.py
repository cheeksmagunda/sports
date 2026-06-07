"""Loss-decomposition analysis for the WNBA Oracle picker.

Decomposes the gap from "our picked lineup" to "winning lineup" into:
  (a) PROJECTION ERROR  -- bad per-player predictions
  (b) CONSTRUCTION ERROR -- given perfect projections, the optimal C(N,5)
  (c) OWNERSHIP / LEVERAGE ERROR  -- chalk vs unique picks
  (d) IRREDUCIBLE VARIANCE  -- median rank1 - rank100 gap

Two regimes:
  1. LIVE: frozen_lineups in Postgres (our actual production picks).
  2. SIMULATED: re-run the heuristic on historical slates.

Outputs the markdown report to research/internal/02_loss_decomposition.md.
"""
from __future__ import annotations

import json
import os
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

# ---- Setup ----
os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_PUBLIC_URL", os.environ.get("DATABASE_URL", "")
)
import sqlalchemy as sa  # noqa: E402

from wnba_oracle.db.engine import get_engine  # noqa: E402

SLOT_MULTS = np.array([2.0, 1.8, 1.6, 1.4, 1.2])


def lineup_score(real_scores: np.ndarray, boosts: np.ndarray) -> float:
    """Compute realized lineup_score with rearrangement-inequality slot assignment.

    Highest realized real_score -> highest slot multiplier (the platform applies
    the same rule the optimizer assumes). final = sum_i rs_i * (slot_i + boost_i).
    """
    order = np.argsort(real_scores, kind="stable")[::-1]
    rs_sorted = real_scores[order]
    boosts_sorted = boosts[order]
    return float(np.sum(rs_sorted * (SLOT_MULTS + boosts_sorted)))


def heuristic_pred(card_boost: float) -> float:
    return max(0.5, 3.16 - 0.45 * float(card_boost))


def picker_visible_value(pred: float, boost: float) -> float:
    """Same as src/picker/optimize.py stage-1 filter."""
    return pred * (2.0 + boost)


def simulate_heuristic_pick(menu: pd.DataFrame, top_n: int = 30) -> list[int]:
    """Reproduce roughly what the picker would freeze using the heuristic.

    The full prod path samples a copula + scores against an expected-payout
    curve, but for a loss-decomposition baseline the dominant first-order
    decision is the visible-value ranking (stage 1) followed by argmax
    expected score under the slot scheme. We approximate stage-2 by picking
    the 5-combo with the highest deterministic E[lineup_score] given the
    heuristic prediction. Team cap = 2 (job2 prod setting).
    """
    menu = menu.copy().reset_index(drop=True)
    menu["pred"] = menu["card_boost"].apply(heuristic_pred)
    menu["vv"] = menu.apply(lambda r: picker_visible_value(r["pred"], r["card_boost"]), axis=1)
    menu = menu.sort_values("vv", ascending=False, kind="stable").head(top_n).reset_index(drop=True)

    teams = menu["team_key"].fillna("").tolist()
    preds = menu["pred"].to_numpy()
    boosts = menu["card_boost"].to_numpy()
    n = len(menu)
    n_teams = len({t for t in teams if t})
    cap = 5 if n_teams <= 2 else (max(2, 3) if n_teams <= 4 else 2)

    best = -np.inf
    best_combo: tuple[int, ...] = ()
    for combo in combinations(range(n), 5):
        # team cap
        if cap < 5:
            counts: dict[str, int] = {}
            ok = True
            for i in combo:
                t = teams[i]
                if not t:
                    continue
                counts[t] = counts.get(t, 0) + 1
                if counts[t] > cap:
                    ok = False
                    break
            if not ok:
                continue
        ls = lineup_score(preds[list(combo)], boosts[list(combo)])
        if ls > best:
            best = ls
            best_combo = combo
    return [int(menu.iloc[i]["platform_player_id"]) for i in best_combo]


def optimal_realized_lineup(menu: pd.DataFrame) -> tuple[float, list[int]]:
    """Perfect-hindsight optimum: pick the 5 menu players that maximize the
    realized lineup_score under team cap=2 (prod constraint).
    """
    menu = menu.dropna(subset=["real_score"]).reset_index(drop=True)
    if len(menu) < 5:
        return float("nan"), []
    teams = menu["team_key"].fillna("").tolist()
    rs = menu["real_score"].to_numpy()
    boosts = menu["card_boost"].to_numpy()
    n = len(menu)
    n_teams = len({t for t in teams if t})
    cap = 5 if n_teams <= 2 else (max(2, 3) if n_teams <= 4 else 2)

    best = -np.inf
    best_combo: tuple[int, ...] = ()
    for combo in combinations(range(n), 5):
        if cap < 5:
            counts: dict[str, int] = {}
            ok = True
            for i in combo:
                t = teams[i]
                if not t:
                    continue
                counts[t] = counts.get(t, 0) + 1
                if counts[t] > cap:
                    ok = False
                    break
            if not ok:
                continue
        ls = lineup_score(rs[list(combo)], boosts[list(combo)])
        if ls > best:
            best = ls
            best_combo = combo
    return float(best), [int(menu.iloc[i]["platform_player_id"]) for i in best_combo]


def perfect_projection_lineup(menu: pd.DataFrame) -> tuple[float, list[int]]:
    """Same as optimal_realized_lineup (perfect hindsight). Alias for clarity."""
    return optimal_realized_lineup(menu)


def winner_score(eng: sa.Engine, slate_date: str) -> float:
    with eng.connect() as conn:
        r = conn.execute(
            sa.text("SELECT score FROM contest_leaderboards WHERE slate_date=:d AND rank=1"),
            {"d": slate_date},
        ).fetchone()
    return float(r[0]) if r else float("nan")


def rank_n_score(eng: sa.Engine, slate_date: str, n: int) -> float | None:
    with eng.connect() as conn:
        r = conn.execute(
            sa.text(
                "SELECT score FROM contest_leaderboards WHERE slate_date=:d AND rank=:r"
            ),
            {"d": slate_date, "r": n},
        ).fetchone()
    return float(r[0]) if r else None


def winner_lineup(eng: sa.Engine, slate_date: str) -> list[dict]:
    with eng.connect() as conn:
        r = conn.execute(
            sa.text(
                "SELECT lineup FROM contest_leaderboards WHERE slate_date=:d AND rank=1 LIMIT 1"
            ),
            {"d": slate_date},
        ).fetchone()
    if not r:
        return []
    lu = r[0]
    if isinstance(lu, str):
        lu = json.loads(lu)
    return lu or []


def get_slate_menu(eng: sa.Engine, slate_date: str) -> pd.DataFrame:
    q = sa.text(
        "SELECT platform_player_id, display_name, team_key, card_boost, drafts, real_score "
        "FROM slate_labels WHERE slate_date=:d"
    )
    with eng.connect() as conn:
        rows = conn.execute(q, {"d": slate_date}).fetchall()
    df = pd.DataFrame(rows, columns=["platform_player_id", "display_name", "team_key", "card_boost", "drafts", "real_score"])
    # de-dup: occasionally a player appears in multiple sections
    df = df.drop_duplicates("platform_player_id").reset_index(drop=True)
    return df


def realized_lineup_score_for(menu: pd.DataFrame, player_ids: list[int]) -> float:
    sub = menu.set_index("platform_player_id").loc[player_ids]
    if sub["real_score"].isna().any():
        return float("nan")
    return lineup_score(sub["real_score"].to_numpy(), sub["card_boost"].to_numpy())


def frozen_lineups(eng: sa.Engine) -> pd.DataFrame:
    q = sa.text(
        "SELECT slate_date::text, entry_recommendation, expected_payout, lineup "
        "FROM frozen_lineups ORDER BY slate_date"
    )
    with eng.connect() as conn:
        rows = conn.execute(q).fetchall()
    out = []
    for sd, flag, ev, lu in rows:
        if isinstance(lu, str):
            lu = json.loads(lu)
        per = lu.get("per_player", []) if isinstance(lu, dict) else []
        if len(per) != 5:
            continue
        out.append({
            "slate_date": sd,
            "flag": flag,
            "ev": ev,
            "player_ids": [int(p["player_id"]) for p in per],
            "preds": [float(p.get("pred_real_score_p50", 0.0)) for p in per],
        })
    return pd.DataFrame(out)


def decompose_one_slate(
    eng: sa.Engine,
    slate_date: str,
    our_pids: list[int] | None,
    our_preds: list[float] | None,
) -> dict:
    menu = get_slate_menu(eng, slate_date)
    if menu.empty or menu["real_score"].isna().all():
        return {"slate_date": slate_date, "skip_reason": "no menu/labels"}

    win_score = winner_score(eng, slate_date)
    rank_20 = rank_n_score(eng, slate_date, 20)  # proxy for "good but realistic"
    # rank-20 to rank-100 isn't available (DB only stores top 20). Use rank20 as
    # a "good entry" proxy and treat the 1-20 spread as observable variance.
    rank20_to_1_gap = win_score - rank_20 if rank_20 is not None else float("nan")

    # Best possible lineup on this slate, assuming perfect knowledge of real_score
    perfect, perfect_ids = optimal_realized_lineup(menu)

    # What our heuristic would have picked (simulated)
    sim_pids = simulate_heuristic_pick(menu)
    sim_realized = realized_lineup_score_for(menu, sim_pids)

    # Our actual picks (if we have them; from frozen_lineups)
    if our_pids is not None and all(pid in menu["platform_player_id"].values for pid in our_pids):
        our_realized = realized_lineup_score_for(menu, our_pids)
        sub = menu.set_index("platform_player_id").loc[our_pids]
        if our_preds is not None and len(our_preds) == len(our_pids):
            preds_arr = np.array(our_preds)
        else:
            preds_arr = sub["card_boost"].apply(heuristic_pred).to_numpy()
        proj_err = preds_arr - sub["real_score"].to_numpy()
        proj_rmse = float(np.sqrt(np.mean(proj_err ** 2)))
        proj_bias = float(np.mean(proj_err))
    else:
        # fall back to simulation
        our_pids = sim_pids
        our_realized = sim_realized
        sub = menu.set_index("platform_player_id").loc[our_pids]
        preds_arr = sub["card_boost"].apply(heuristic_pred).to_numpy()
        proj_err = preds_arr - sub["real_score"].to_numpy()
        proj_rmse = float(np.sqrt(np.mean(proj_err ** 2)))
        proj_bias = float(np.mean(proj_err))

    # CONSTRUCTION ERROR: gap between "our pick" and "perfect hindsight"
    construction_gap = perfect - our_realized

    # Counterfactual: if we kept our heuristic predictions, what would
    # the optimal lineup under our predictions be? That tells us how much
    # of our gap is PROJECTION (pred wrong) vs CONSTRUCTION (pred right
    # but combo suboptimal).
    # "Best lineup the heuristic could have chosen": that's exactly sim_pids,
    # so sim_realized is "the score we'd get with perfect optimizer + heuristic pred"
    # The projection-induced loss = perfect - sim_realized (the gap our heuristic
    # leaves on the table because it ranks players wrong).
    projection_loss = perfect - sim_realized
    # Construction loss our actual frozen lineup ate vs the heuristic-optimal: 0
    # if frozen == sim, else >= 0. (Captures live serving drift, name-mismatch
    # bugs, etc.) For live slates the frozen may differ from our re-sim.
    construction_loss_extra = max(0.0, sim_realized - our_realized)

    # OWNERSHIP / LEVERAGE ERROR: how much of our pool overlap with the winner?
    win_lu = winner_lineup(eng, slate_date)
    win_pids = [int(p.get("playerId", p.get("id", -1))) for p in win_lu]
    win_pids = [p for p in win_pids if p > 0]
    overlap_with_winner = len(set(our_pids) & set(win_pids))
    # Top-20 chalkiness: count of winner players that finished above median drafts
    # vs below.
    if menu["drafts"].notna().any():
        median_drafts = float(menu["drafts"].median())
        our_drafts = sub["drafts"].fillna(0).to_numpy()
        chalk_picks = int(np.sum(our_drafts > median_drafts))
    else:
        median_drafts = float("nan")
        chalk_picks = -1

    # Gap to winner
    gap_to_winner = win_score - our_realized

    return {
        "slate_date": slate_date,
        "win_score": win_score,
        "rank20_score": rank_20,
        "rank1_to_rank20_gap": rank20_to_1_gap,
        "perfect_score": perfect,
        "our_score": our_realized,
        "sim_heuristic_score": sim_realized,
        "gap_to_winner": gap_to_winner,
        "gap_to_perfect": perfect - our_realized,
        "projection_loss": projection_loss,
        "construction_loss_extra": construction_loss_extra,
        "proj_rmse": proj_rmse,
        "proj_bias": proj_bias,
        "overlap_with_winner": overlap_with_winner,
        "chalk_picks": chalk_picks,
        "median_drafts": median_drafts,
        "n_menu": int(len(menu)),
        "n_with_score": int(menu["real_score"].notna().sum()),
        "our_pids": our_pids,
        "win_pids": win_pids,
        "perfect_pids": perfect_ids,
        "sim_pids": sim_pids,
    }


def main():
    eng = get_engine()
    # 1) Live frozen lineups
    fl = frozen_lineups(eng)
    print(f"Frozen lineups with 5 picks: {len(fl)}")

    # 2) Pick ~30 historical slates spread 2025-06 -> 2026-05
    with eng.connect() as conn:
        rows = conn.execute(sa.text(
            "SELECT DISTINCT slate_date FROM slate_labels WHERE real_score IS NOT NULL "
            "ORDER BY slate_date"
        )).fetchall()
    all_dates = [r[0] for r in rows]
    print(f"Total slates with real_score: {len(all_dates)}")
    # Filter to 2025-06 .. 2026-05 range
    sample_dates = [d for d in all_dates if "2025-06" <= str(d)[:7] <= "2026-05"]
    # Take 30 evenly spaced
    if len(sample_dates) > 30:
        step = max(1, len(sample_dates) // 30)
        sample_dates = sample_dates[::step][:30]
    print(f"Sampled {len(sample_dates)} historical slates")

    results = []

    # First: process each frozen-lineup slate with the actual picks
    fl_dates = set(fl["slate_date"].tolist())
    for _, row in fl.iterrows():
        sd = row["slate_date"]
        r = decompose_one_slate(eng, sd, row["player_ids"], row["preds"])
        r["source"] = "LIVE"
        r["flag"] = row["flag"]
        r["ev"] = row["ev"]
        results.append(r)

    # Now process historical sample (simulated) -- but skip dates we already
    # have as live frozen, and skip dates where we know real_score coverage
    # is too thin.
    for sd in sample_dates:
        if sd in fl_dates:
            continue
        r = decompose_one_slate(eng, sd, None, None)
        r["source"] = "SIM"
        r["flag"] = "sim"
        r["ev"] = float("nan")
        results.append(r)

    # Also explicitly include the RESULTS.md hand-recorded 2026-05-28 lineup:
    # M. Siegrist (player_id?), Zandalasini, Parker-Tyus, R. Johnson, VanSlooten
    # Look them up by display_name
    menu_528 = get_slate_menu(eng, "2026-05-28")
    name_map = {n.lower(): pid for n, pid in zip(menu_528["display_name"], menu_528["platform_player_id"])}
    cand_names = ["m. siegrist", "c. zandalasini", "c. parker-tyus", "r. johnson", "g. vanslooten"]
    matched = []
    for n in cand_names:
        for k, pid in name_map.items():
            if n in k.lower() or k.lower() in n:
                matched.append(int(pid))
                break
    if len(matched) == 5:
        r = decompose_one_slate(eng, "2026-05-28", matched, None)
        r["source"] = "LIVE_SCREENSHOT_528"
        r["flag"] = "enter_with_caveat"
        r["ev"] = float("nan")
        results.append(r)

    df = pd.DataFrame(results)
    df.to_csv("/Users/hanslarson/Desktop/wnba-oracle/research/internal/_loss_decomp_data.csv", index=False)
    print(f"\nWrote {len(df)} rows")
    print(df.head().to_string())

    # ---- Summary stats ----
    print("\n=== Summary across all slates ===")
    print(df[["gap_to_winner", "gap_to_perfect", "projection_loss", "construction_loss_extra", "proj_rmse", "proj_bias", "overlap_with_winner"]].describe().to_string())

    # Split LIVE vs SIM
    print("\n=== LIVE only ===")
    live_df = df[df["source"].str.startswith("LIVE")]
    print(live_df[["slate_date","win_score","our_score","gap_to_winner","gap_to_perfect","projection_loss","proj_rmse","proj_bias","overlap_with_winner","chalk_picks","flag"]].to_string())

    print("\n=== SIM summary ===")
    sim_df = df[df["source"] == "SIM"]
    print(sim_df[["gap_to_winner","gap_to_perfect","projection_loss","proj_rmse","proj_bias","overlap_with_winner"]].describe().to_string())


if __name__ == "__main__":
    main()
