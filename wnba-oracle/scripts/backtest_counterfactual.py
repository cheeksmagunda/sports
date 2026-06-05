"""Counterfactual backtest: attribute the picker's leaderboard gap to its
levers (contrarian strength, team-cap policy) and measure raw prediction
quality. Reuses the real job2 pipeline so deltas reflect production code.

Configs swept on the 16 2026 slates:
  A  current prod         contrarian=0.2, cap=2 static
  B  contrarian OFF       contrarian=0.0, cap=2 static
  C  dynamic cap          contrarian=0.2, cap=dynamic(games)
  D  both fixes           contrarian=0.0, cap=dynamic(games)

Dynamic cap policy (proposed): 1 game -> 5 (uncapped; pigeonhole forces 3+),
2 games -> 3, 3+ games -> 2 (matches observed winner stacking; see
analyze_strategy_gap.py).

Diagnostics:
  - prediction quality: Spearman(pred ceil_contrib, realized) per slate
  - selection quality: how many of the realized top-8 plays each policy's
    5 picks recover, vs a boost-only baseline and the realized oracle.

Leakage caveat (same as backtest_pipeline.py): the EB artifact saw these
slates, so ABSOLUTE placement is optimistic. Config-to-config DELTAS hold
the leakage constant and are the trustworthy signal.

Run: uv run python scripts/backtest_counterfactual.py
"""
from __future__ import annotations

import itertools
import json
import os
import sys
from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault(
    "WNBA_ORACLE_MODEL_ARTIFACT_SHA",
    "000f54fe08b47a20504d" + "0" * 44,  # prefix-match latest artifact; sidecar holds full
)
os.environ.setdefault("PAYOUT_REGIME", "top_20")

# Use the full SHA of the latest artifact (picker_2a2fe836).
_SHA_FILE = Path(__file__).resolve().parents[1] / "models" / "picker_2a2fe836_1779943299.sha256"
if _SHA_FILE.exists():
    os.environ["WNBA_ORACLE_MODEL_ARTIFACT_SHA"] = _SHA_FILE.read_text().strip()

from wnba_oracle.picker.optimize import (  # noqa: E402
    DEFAULT_SLOT_MULTIPLIERS,
    OptimizeConfig,
    optimize_lineup,
)
from wnba_oracle.picker.payout import default_curve_for_regime  # noqa: E402
from wnba_oracle.picker.popularity import ContrarianConfig  # noqa: E402
from wnba_oracle.scheduler.job2 import _build_specs, _load_player_history  # noqa: E402

SLOTS = tuple(DEFAULT_SLOT_MULTIPLIERS)


def dynamic_cap(n_games: float) -> int:
    if n_games <= 1:
        return 5
    if n_games <= 2:
        return 3
    return 2


def score_truth(pids, boost_by, rs_by) -> float:
    members = sorted(((p, rs_by.get(int(p), 0.0)) for p in pids), key=lambda x: -x[1])
    return sum((SLOTS[i] + boost_by.get(int(p), 0.0)) * rs for i, (p, rs) in enumerate(members))


def realized_oracle(pool_rows, cap: int) -> float:
    # Prune to the top-26 by realized ceiling contribution before the C(n,5)
    # brute force: a player outside the top-26 by real_score*(2.0+boost)
    # cannot plausibly enter the top-5-by-ceiling lineup, and this keeps the
    # enumeration at C(26,5)=65k instead of C(37,5)=435k.
    pool_rows = sorted(
        pool_rows, key=lambda r: -(r["real_score"] * (2.0 + r["card_boost"]))
    )[:26]
    vals = np.array([r["real_score"] for r in pool_rows], float)
    boosts = np.array([r["card_boost"] for r in pool_rows], float)
    teams = np.array([r["team_key"] for r in pool_rows])
    best = -1.0
    for combo in itertools.combinations(range(len(pool_rows)), 5):
        idx = list(combo)
        _, c = np.unique(teams[idx], return_counts=True)
        if c.max() > cap:
            continue
        v, b = vals[idx], boosts[idx]
        o = np.argsort(v)[::-1]
        best = max(best, float(np.sum(v[o] * (np.array(SLOTS) + b[o]))))
    return best


def run_config(slates_data, *, contrarian_strength: float, cap_mode: str):
    """cap_mode in {'static2','dynamic'}. Tests the production toggle directly:
    'static2' = max_per_team=2 with dynamic_team_cap OFF; 'dynamic' = the same
    base cap of 2 but dynamic_team_cap ON (the optimizer relaxes small slates
    internally). Returns list of per-slate dicts."""
    out = []
    for sd, _slate, slate_lb, enrichment, boost_by, rs_by, n_games in slates_data:
        cc = ContrarianConfig(enabled=contrarian_strength > 0, strength=contrarian_strength)
        samps, fields, _ = _build_specs(
            enrichment, slate_date=sd, contrarian_cfg=cc, player_history=_HISTORY
        )
        if len(samps) < 5:
            continue
        cfg = OptimizeConfig(
            top_n_filter=min(18, len(samps)), n_samples=150, n_field_lineups=40,
            seed=2026, max_per_team=2, dynamic_team_cap=(cap_mode == "dynamic"),
        )
        try:
            rec = optimize_lineup(samps, fields, default_curve_for_regime("top_20"), cfg=cfg)
            our = score_truth(rec.player_ids, boost_by, rs_by)
            our_pids = {int(p) for p in rec.player_ids}
        except Exception:
            our, our_pids = 0.0, set()
        scores = sorted(slate_lb["score"].to_list(), reverse=True)
        placement = sum(1 for s in scores if s >= our) + 1
        win_pids = {int(p["playerId"]) for p in json.loads(slate_lb.row(0, named=True)["lineup_json"])}
        out.append({
            "slate": sd, "our": our, "top1": scores[0], "top20": scores[-1],
            "placement": placement, "overlap": len(our_pids & win_pids), "n_games": n_games,
        })
    return out


def agg(rows, label):
    n = len(rows)
    t20 = sum(1 for r in rows if r["placement"] <= 20)
    t5 = sum(1 for r in rows if r["placement"] <= 5)
    t1 = sum(1 for r in rows if r["placement"] == 1)
    gap = np.mean([r["top1"] - r["our"] for r in rows])
    ov = np.mean([r["overlap"] for r in rows])
    beat20 = np.mean([r["our"] >= r["top20"] for r in rows])
    print(f"  {label:28s} top20={t20:2d}/{n}  top5={t5:2d}  top1={t1}  "
          f"mean_gap={gap:5.2f}  overlap={ov:.2f}/5  beat_cashline={beat20:4.0%}")


_HISTORY = _load_player_history()


def main() -> int:
    from wnba_oracle.db.reads import read_leaderboards, read_slate_labels

    sl = read_slate_labels()
    lb = read_leaderboards()
    test = sorted(d for d in sl["slate_date"].unique().to_list() if d.startswith("2026-"))

    slates_data = []
    for sd in test:
        slate = sl.filter(pl.col("slate_date") == sd).unique(subset=["platform_player_id"])
        slate_lb = lb.filter(pl.col("slate_date") == sd).sort("rank")
        if not slate_lb.height:
            continue
        teams = slate["team_key"].unique().to_list()
        n_games = len(teams) / 2.0
        team_to_opp = {t: teams[(i + 1) % len(teams)] for i, t in enumerate(teams)}
        enrichment, boost_by, rs_by = [], {}, {}
        for r in slate.iter_rows(named=True):
            pid = int(r["platform_player_id"])
            boost_by[pid] = float(r["card_boost"])
            rs_by[pid] = float(r["real_score"]) if r["real_score"] is not None else 0.0
            enrichment.append({
                "real_sports_player_id": str(pid), "name": r["display_name"],
                "team": r["team_key"], "opponent": team_to_opp.get(r["team_key"], "UNK"),
                "position": "F", "card_boost": float(r["card_boost"]), "features_json": "{}",
            })
        slates_data.append((sd, slate, slate_lb, enrichment, boost_by, rs_by, n_games))

    print(f"Counterfactual backtest on {len(slates_data)} 2026 slates")
    print("(absolute numbers optimistic due to EB leakage; trust the config DELTAS)\n")

    print("=== CONFIG SWEEP ===")
    agg(run_config(slates_data, contrarian_strength=0.2, cap_mode="static2"), "A prod (contr=0.2, cap2)")
    agg(run_config(slates_data, contrarian_strength=0.0, cap_mode="static2"), "B contrarian OFF")
    agg(run_config(slates_data, contrarian_strength=0.2, cap_mode="dynamic"), "C dynamic cap")
    agg(run_config(slates_data, contrarian_strength=0.0, cap_mode="dynamic"), "D both fixes")

    # ---- prediction & selection quality ----
    print("\n=== PREDICTION QUALITY (per-slate Spearman of pred vs realized ceil_contrib) ===")
    sps, recov_pred, recov_boost = [], [], []
    oracle_cap2, oracle_dyn, win_scores = [], [], []
    for sd, slate, slate_lb, enrichment, boost_by, rs_by, n_games in slates_data:
        cc = ContrarianConfig(enabled=False, strength=0.0)
        samps, fields, _ = _build_specs(enrichment, slate_date=sd, contrarian_cfg=cc, player_history=_HISTORY)
        if len(samps) < 6:
            continue
        pid = [s.player_id for s in fields]
        pred = np.array([f.pred_real_score * (2.0 + f.card_boost) for f in fields])
        realized = np.array([rs_by.get(int(p), 0.0) * (2.0 + boost_by.get(int(p), 0.0)) for p in pid])
        boost_only = np.array([2.0 + boost_by.get(int(p), 0.0) for p in pid])
        rho = spearmanr(pred, realized).correlation
        if not np.isnan(rho):
            sps.append(rho)
        # realized top-8 set
        top8 = set(np.argsort(realized)[::-1][:8].tolist())
        pred_top5 = set(np.argsort(pred)[::-1][:5].tolist())
        boost_top5 = set(np.argsort(boost_only)[::-1][:5].tolist())
        recov_pred.append(len(pred_top5 & top8))
        recov_boost.append(len(boost_top5 & top8))
        pool_rows = list(slate.iter_rows(named=True))
        oracle_cap2.append(realized_oracle(pool_rows, 2) if n_games > 1 else float("nan"))
        oracle_dyn.append(realized_oracle(pool_rows, dynamic_cap(n_games)))
        win_scores.append(float(slate_lb.row(0, named=True)["score"]))
    print(f"  mean Spearman(pred, realized)       = {np.nanmean(sps):+.3f}  "
          f"(0 = our ranking is noise; 1 = perfect)")
    print(f"  our pred top-5 recovers {np.mean(recov_pred):.2f}/5 of the realized top-8 plays")
    print(f"  boost-ONLY top-5 recovers {np.mean(recov_boost):.2f}/5 of the realized top-8 plays")
    print("    (if boost-only ~= our pred, the model adds little over the boost tier)\n")

    print("=== CEILING: realized oracle vs actual human winner ===")
    print(f"  mean realized-oracle (dynamic cap)  = {np.nanmean(oracle_dyn):.2f}")
    print(f"  mean realized-oracle (static cap 2) = {np.nanmean([o for o in oracle_cap2 if not np.isnan(o)]):.2f} "
          f"(2+ game slates only)")
    print(f"  mean actual human winner            = {np.mean(win_scores):.2f}  "
          f"({np.mean(win_scores)/np.nanmean(oracle_dyn):.0%} of oracle)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
