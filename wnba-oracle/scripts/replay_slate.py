"""Replay one slate through the picker, old config vs shipped config, and
print the lineup we would have produced vs the actual winner + oracle.

Honest (walk-forward, no leakage): predictions use only slates < target.
Default predictor is boost_prior (the D52 walk-forward winner); pass
--eb to also show the EB-artifact-style predictor.

Usage: uv run python scripts/replay_slate.py [SLATE_DATE]   # default 2026-05-25
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

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.popularity import (
    ContrarianConfig,
    apply_contrarian_adjustment,
    slate_labels_to_popularity,
)
from wnba_oracle.picker.sample import PlayerSamplingSpec
from wnba_oracle.predict.base import boost_prior, player_volatility

SLOTS = [2.0, 1.8, 1.6, 1.4, 1.2]


def prior_by_player(history: pd.DataFrame) -> dict[int, list[float]]:
    h = history.sort_values("slate_date", ascending=False)
    return {int(pid): g["real_score"].tolist() for pid, g in h.groupby("player_id")}


def score_truth(pids, boost_by, rs_by):
    members = sorted(((p, rs_by.get(int(p), 0.0)) for p in pids), key=lambda x: -x[1])
    return sum((SLOTS[i] + boost_by.get(int(p), 0.0)) * rs for i, (p, rs) in enumerate(members))


def oracle(pool, cap):
    rows = pool.to_dict("records")
    best, _combo = -1.0, None
    teams = [r["team"] for r in rows]
    for c in itertools.combinations(range(len(rows)), 5):
        t = [teams[i] for i in c]
        if max(t.count(x) for x in set(t)) > cap:
            continue
        v = sorted(((rows[i]["real_score"], rows[i]["card_boost"]) for i in c), key=lambda x: -x[0])
        s = sum(val * (SLOTS[j] + b) for j, (val, b) in enumerate(v))
        if s > best:
            best, _combo = s, c
    return best


def build_and_pick(pool, prior, drafts, *, K, per_player_sigma, dynamic_cap):
    boost_by = {int(r.player_id): float(r.card_boost) for r in pool.itertuples()}
    preds = {p: boost_prior(b) for p, b in boost_by.items()}
    pop = slate_labels_to_popularity(drafts)
    adj = apply_contrarian_adjustment(preds, pop, ContrarianConfig(enabled=True, strength=0.2))
    vol = player_volatility(prior)
    teams = pool["team"].unique().tolist()
    opp = {t: teams[(i + 1) % len(teams)] for i, t in enumerate(teams)}
    samps, fields = [], []
    for r in pool.itertuples():
        pid = int(r.player_id)
        pred = max(0.5, adj[pid])
        mu = float(np.log(max(pred + K, 1.0)))
        sigma = (
            min(0.6, max(0.12, vol.get(pid, 1.17) / max(pred + K, 1e-6)))
            if per_player_sigma
            else 0.25
        )
        samps.append(
            PlayerSamplingSpec(
                pid, str(r.team), str(opp.get(r.team, "")), mu, sigma, float(r.card_boost)
            )
        )
        fields.append(FieldPlayerSpec(pid, pred, float(r.card_boost)))
    cfg = OptimizeConfig(
        top_n_filter=min(20, len(samps)),
        n_samples=4000,
        n_field_lineups=200,
        seed=2026,
        max_per_team=2,
        dynamic_team_cap=dynamic_cap,
        score_offset=K,
    )
    return optimize_lineup(samps, fields, default_curve_for_regime("top_20"), cfg=cfg)


def main() -> int:
    sd = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "2026-05-25"
    from wnba_oracle.db.reads import read_label_corpus, read_leaderboards, read_slate_labels

    corpus = read_label_corpus().to_pandas()
    lb = read_leaderboards().filter(pl.col("slate_date") == sd).sort("rank")
    sl = read_slate_labels().filter(pl.col("slate_date") == sd)

    pool = corpus[corpus["slate_date"] == sd].drop_duplicates("player_id").reset_index(drop=True)
    prior = prior_by_player(corpus[corpus["slate_date"] < sd])
    drafts = {
        int(r["platform_player_id"]): int(r["drafts"])
        for r in sl.iter_rows(named=True)
        if r["drafts"] is not None
    }
    name_by = {int(r.player_id): r.display_name for r in pool.itertuples()}
    boost_by = {int(r.player_id): float(r.card_boost) for r in pool.itertuples()}
    rs_by = {int(r.player_id): float(r.real_score) for r in pool.itertuples()}
    n_teams = pool["team"].nunique()

    scores = sorted(lb["score"].to_list(), reverse=True)
    win_row = lb.row(0, named=True)
    win_pids = {int(p["playerId"]) for p in json.loads(win_row["lineup_json"])}

    print(f"=== {sd}  ({n_teams} teams / {n_teams // 2} games, pool={len(pool)}) ===")
    print(
        f"winner {win_row['user_id']}: {win_row['score']:.2f} | top-5 line {scores[4]:.2f} | "
        f"top-20 (cash) line {scores[-1]:.2f} | oracle(dyn cap)={oracle(pool, 5 if n_teams <= 2 else 3 if n_teams <= 4 else 2):.2f}"
    )
    print()

    def show(label, rec):
        our = score_truth(rec.player_ids, boost_by, rs_by)
        place = sum(1 for s in scores if s >= our) + 1
        ov = len({int(p) for p in rec.player_ids} & win_pids)
        verdict = "WIN" if our > scores[0] else ("CASH(top20)" if our >= scores[-1] else "miss")
        print(f"{label}: {our:.2f}  place ~{place}  overlap {ov}/5 winner  [{verdict}]")
        members = sorted(
            ((p, rs_by.get(int(p), 0.0), boost_by.get(int(p), 0.0)) for p in rec.player_ids),
            key=lambda x: -x[1],
        )
        for i, (p, rs, b) in enumerate(members):
            star = "*" if int(p) in win_pids else " "
            print(
                f"   {star}{name_by.get(int(p), p):16s} boost {b:.1f}  real {rs:.2f}  x{SLOTS[i] + b:.1f} = {(SLOTS[i] + b) * rs:5.2f}"
            )

    old = build_and_pick(pool, prior, drafts, K=10.0, per_player_sigma=False, dynamic_cap=False)
    new = build_and_pick(pool, prior, drafts, K=2.0, per_player_sigma=True, dynamic_cap=True)
    show("OLD (K10, flat sigma, static cap)", old)
    print()
    show("NEW shipped (K2, per-player sigma, dyn cap)", new)
    print(f"\n(* = also in winner {win_row['user_id']}'s lineup)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
