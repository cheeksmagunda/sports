"""Ship gate: minutes x rate predictor vs boost_prior on walk-forward PLACEMENT.

Builds per-player prior (real_score, minutes) series from the joined corpus and
predicts E[real] with predict/minutes.py (recency baseline only -- the corpus
has no historical RotoWire/Vegas, so the same-day role adjustments are off here;
they only add on top in live). Both configs use the shipped sampling (K=2,
per-player sigma), dynamic cap, contrarian 0.2. Deltas are the signal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from validate_minutes_model import load_joined
from wnba_oracle.predict.form import boost_prior

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.popularity import (
    ContrarianConfig,
    apply_contrarian_adjustment,
    slate_labels_to_popularity,
)
from wnba_oracle.picker.sample import PlayerSamplingSpec
from wnba_oracle.predict.minutes import (
    MinutesConfig,
    blended_real_score,
    minutes_volatility,
    per_minute_rate,
    predict_real_score,
    recent_minutes,
)

SLOTS = [2.0, 1.8, 1.6, 1.4, 1.2]


def build_histories(matched: pd.DataFrame):
    """{player_id: list of (slate_date, real, min) sorted ascending}."""
    matched = matched.sort_values(["player_id", "slate_date"])
    hist = {}
    for pid, g in matched.groupby("player_id"):
        hist[int(pid)] = list(zip(g["slate_date"], g["real_score"], g["min"], strict=True))
    return hist


def prior_series(hist, pid, sd):
    """(prior_real, prior_min) most-recent-first, strictly before sd."""
    rows = [(d, r, m) for (d, r, m) in hist.get(int(pid), []) if d < sd]
    rows = rows[::-1]
    return [r for _, r, _ in rows], [m for _, _, m in rows]


def predict_slate(pool, hist, mode, cfg, k0=3.0):
    out = {}
    for r in pool.itertuples():
        pid = int(r.player_id)
        pr, pm = prior_series(hist, pid, r.slate_date)
        bp = boost_prior(r.card_boost)
        if mode == "boost":
            out[pid] = bp
        elif mode == "minutes":
            out[pid] = predict_real_score(pr, pm, cfg=cfg) if len(pm) >= cfg.min_obs_for_history else bp
        else:  # blend: the shipped canonical predictor (minutes.blended_real_score)
            out[pid] = blended_real_score(
                recent_min=recent_minutes(pm, cfg=cfg),
                rate=per_minute_rate(pr, pm, cfg=cfg),
                n_games=len(pm), boost_prior=bp, cfg=cfg,
            )
    return out


def run(matched, lb, slates, mode):
    cfg = MinutesConfig()
    cc = ContrarianConfig(enabled=True, strength=0.2)
    curve = default_curve_for_regime("top_20")
    hist = build_histories(matched)
    out = []
    for sd in slates:
        pool = matched[matched["slate_date"] == sd].drop_duplicates("player_id")
        lb_s = lb.filter(pl.col("slate_date") == sd).sort("rank")
        if len(pool) < 6 or not lb_s.height:
            continue
        preds = predict_slate(pool, hist, mode, cfg)
        drafts = {int(r.player_id): int(r.drafts) for r in pool.itertuples()
                  if "drafts" in pool.columns and pd.notna(r.drafts)}
        adj = apply_contrarian_adjustment(preds, slate_labels_to_popularity(drafts), cc)
        boost_by = {int(r.player_id): float(r.card_boost) for r in pool.itertuples()}
        rs_by = {int(r.player_id): float(r.real_score) for r in pool.itertuples()}
        teams = pool["team"].unique().tolist()
        opp = {t: teams[(i + 1) % len(teams)] for i, t in enumerate(teams)}
        K = 2.0
        samps, fields = [], []
        for r in pool.itertuples():
            pid = int(r.player_id)
            pred = max(0.5, adj[pid])
            mu = float(np.log(max(pred + K, 1.0)))
            if mode == "boost":
                sig_real = 1.17
            else:
                pr, pm = prior_series(hist, pid, sd)
                rate = per_minute_rate(pr, pm, cfg=cfg)
                sig_real = max(0.5, minutes_volatility(pm) * rate)  # minutes vol -> real vol
            sigma = min(0.6, max(0.12, sig_real / max(pred + K, 1e-6)))
            samps.append(PlayerSamplingSpec(pid, str(r.team), str(opp.get(r.team, "")), mu, sigma, float(r.card_boost)))
            fields.append(FieldPlayerSpec(pid, pred, float(r.card_boost)))
        oc = OptimizeConfig(top_n_filter=min(20, len(samps)), n_samples=250, n_field_lineups=60,
                            seed=2026, max_per_team=2, dynamic_team_cap=True, score_offset=K)
        rec = optimize_lineup(samps, fields, curve, cfg=oc)
        members = sorted(((p, rs_by.get(int(p), 0.0)) for p in rec.player_ids), key=lambda x: -x[1])
        our = sum((SLOTS[i] + boost_by.get(int(p), 0.0)) * rs for i, (p, rs) in enumerate(members))
        scores = sorted(lb_s["score"].to_list(), reverse=True)
        win = {int(p["playerId"]) for p in json.loads(lb_s.row(0, named=True)["lineup_json"])}
        out.append({"our": our, "top1": scores[0], "cash": scores[-1], "top5": scores[4] if len(scores) >= 5 else scores[-1],
                    "ov": len({int(p) for p in rec.player_ids} & win)})
    return out


def main():
    matched = load_joined()
    matched = matched[matched["min"].notna()].copy()
    from wnba_oracle.db.reads import read_leaderboards, read_slate_labels

    lb = read_leaderboards()
    sl = read_slate_labels()
    dm = {(r["slate_date"], int(r["platform_player_id"])): r["drafts"] for r in sl.iter_rows(named=True)}
    matched["drafts"] = [dm.get((d, p)) for d, p in zip(matched["slate_date"], matched["player_id"])]
    slates = sorted(d for d in matched["slate_date"].unique() if str(d).startswith("2026-"))
    print(f"Minutes-predictor placement gate, {len(slates)} 2026 slates (deltas are the signal)\n")
    modes = [m for m in sys.argv[1:] if m in ("boost", "minutes", "blend")] or ["boost", "minutes", "blend"]
    for mode in modes:
        r = run(matched, lb, slates, mode)
        n = len(r)
        cash = sum(1 for x in r if x["our"] >= x["cash"])
        t5 = sum(1 for x in r if x["our"] >= x["top5"])
        win = sum(1 for x in r if x["our"] > x["top1"])
        gap = np.mean([x["top1"] - x["our"] for x in r])
        ov = np.mean([x["ov"] for x in r])
        print(f"  {mode:8s}: cash(top20) {cash:2d}/{n}  top5 {t5}  win {win}  "
              f"mean_gap {gap:5.2f}  overlap {ov:.2f}/5")


if __name__ == "__main__":
    main()
