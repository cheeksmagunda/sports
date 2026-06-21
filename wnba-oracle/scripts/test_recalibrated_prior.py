"""Walk-forward placement: does recalibrating E[real|boost] to the empirical
curve (fade the boost-3 trap, de-bias the ranking) beat the linear boost_prior?

Both configs use the shipped sampling (K=2, per-player sigma), dynamic cap, and
contrarian 0.2. The only difference is the base E[real] predictor:
  boost_prior  -- D43 linear 3.16 - 0.45*boost  (current)
  empirical    -- mean realized real_score per 0.5-width boost bucket, fit on
                  slates < N only (walk-forward safe). Crushes boost-3
                  (1.81 -> ~1.38) and stops the optimizer chasing lottery darts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.popularity import (
    ContrarianConfig,
    apply_contrarian_adjustment,
    slate_labels_to_popularity,
)
from wnba_oracle.picker.sample import PlayerSamplingSpec
from wnba_oracle.predict.form import boost_prior, player_volatility

SLOTS = [2.0, 1.8, 1.6, 1.4, 1.2]


def bucket(b):
    return min(int(b / 0.5) * 0.5, 3.0)


def empirical_curve(history: pd.DataFrame) -> dict[float, float]:
    """mean realized real per boost bucket from the as-of history."""
    if history.empty:
        return {}
    h = history.copy()
    h["bk"] = h["card_boost"].map(bucket)
    return {float(k): float(v) for k, v in h.groupby("bk")["real_score"].mean().items()}


def predict(pool, hist, mode):
    if mode == "boost_prior":
        return {int(r.player_id): boost_prior(r.card_boost) for r in pool.itertuples()}
    curve = empirical_curve(hist)
    return {int(r.player_id): max(0.5, curve.get(bucket(r.card_boost), boost_prior(r.card_boost)))
            for r in pool.itertuples()}


def run(corpus, lb, slates, mode):
    cc = ContrarianConfig(enabled=True, strength=0.2)
    curve = default_curve_for_regime("top_20")
    out = []
    for sd in slates:
        hist = corpus[corpus["slate_date"] < sd]
        pool = corpus[corpus["slate_date"] == sd].drop_duplicates("player_id")
        lb_s = lb.filter(pl.col("slate_date") == sd).sort("rank")
        if len(pool) < 6 or not lb_s.height:
            continue
        preds = predict(pool, hist, mode)
        drafts = {int(r.player_id): int(r.drafts) for r in pool.itertuples()
                  if "drafts" in pool.columns and pd.notna(r.drafts)}
        pop = slate_labels_to_popularity(drafts)
        adj = apply_contrarian_adjustment(preds, pop, cc)
        prior_hist = {int(pid): g.sort_values("slate_date", ascending=False)["real_score"].tolist()
                      for pid, g in hist.groupby("player_id")}
        vol = player_volatility(prior_hist)
        boost_by = {int(r.player_id): float(r.card_boost) for r in pool.itertuples()}
        rs_by = {int(r.player_id): float(r.real_score) for r in pool.itertuples()}
        teams = pool["team"].unique().tolist()
        opp = {t: teams[(i + 1) % len(teams)] for i, t in enumerate(teams)}
        samps, fields = [], []
        K = 2.0
        for r in pool.itertuples():
            pid = int(r.player_id)
            pred = max(0.5, adj[pid])
            mu = float(np.log(max(pred + K, 1.0)))
            sigma = min(0.6, max(0.12, vol.get(pid, 1.17) / max(pred + K, 1e-6)))
            samps.append(PlayerSamplingSpec(pid, str(r.team), str(opp.get(r.team, "")), mu, sigma, float(r.card_boost)))
            fields.append(FieldPlayerSpec(pid, pred, float(r.card_boost)))
        cfg = OptimizeConfig(top_n_filter=min(20, len(samps)), n_samples=250, n_field_lineups=60,
                             seed=2026, max_per_team=2, dynamic_team_cap=True, score_offset=2.0)
        rec = optimize_lineup(samps, fields, curve, cfg=cfg)
        members = sorted(((p, rs_by.get(int(p), 0.0)) for p in rec.player_ids), key=lambda x: -x[1])
        our = sum((SLOTS[i] + boost_by.get(int(p), 0.0)) * rs for i, (p, rs) in enumerate(members))
        scores = sorted(lb_s["score"].to_list(), reverse=True)
        win = {int(p["playerId"]) for p in json.loads(lb_s.row(0, named=True)["lineup_json"])}
        out.append({"our": our, "top1": scores[0], "cash": scores[-1],
                    "place": sum(1 for s in scores if s >= our) + 1,
                    "ov": len({int(p) for p in rec.player_ids} & win)})
    return out


def main():
    from wnba_oracle.db.reads import read_label_corpus, read_leaderboards, read_slate_labels

    corpus = read_label_corpus().to_pandas()
    sl = read_slate_labels()
    drafts_map = {(r["slate_date"], int(r["platform_player_id"])): r["drafts"] for r in sl.iter_rows(named=True)}
    corpus["drafts"] = [drafts_map.get((d, p)) for d, p in zip(corpus["slate_date"], corpus["player_id"])]
    lb = read_leaderboards()
    slates = sorted(d for d in corpus["slate_date"].unique() if str(d).startswith("2026-"))
    print(f"Walk-forward placement on {len(slates)} 2026 slates (deltas are the signal)\n")
    for mode in ("boost_prior", "empirical"):
        r = run(corpus, lb, slates, mode)
        n = len(r)
        t5 = sum(1 for x in r if x["place"] <= 5)
        t1 = sum(1 for x in r if x["place"] == 1)
        cash = sum(1 for x in r if x["our"] >= x["cash"])
        gap = np.mean([x["top1"] - x["our"] for x in r])
        ov = np.mean([x["ov"] for x in r])
        print(f"  {mode:12s}: cash(top20) {cash:2d}/{n}  top5 {t5}  win {t1}  "
              f"mean_gap {gap:5.2f}  overlap {ov:.2f}/5")


if __name__ == "__main__":
    main()
