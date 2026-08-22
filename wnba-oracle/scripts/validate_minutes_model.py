"""Go/no-go: does a minutes x per-minute-rate model beat the boost prior?

Joins the realized real_score corpus to the nba_api minutes backfill, then
walk-forward tests whether decomposing real_score into projected_minutes x
per_minute_rate predicts next-game real_score better than the boost handicap.

If minutes-based E[real] beats boost_prior out-of-sample, we have the edge to
build live. If it ties (like recency did in D52), the edge needs same-day
role signals the corpus can't replay, and we say so.

Run: uv run python scripts/validate_minutes_model.py
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return s.strip().lower()


def boost_prior(b: float) -> float:
    return max(0.5, 3.16 - 0.45 * float(b))


# team-code aliases between corpus team_key and nba_api TEAM_ABBREVIATION
ALIAS = {
    "PHX": "PHO",
    "PHO": "PHO",
    "LV": "LVA",
    "LVA": "LVA",
    "POR": "PDX",
    "PDX": "PDX",
    "GSV": "GSV",
    "GS": "GSV",
}


def alias(t):
    t = str(t or "").upper()
    return ALIAS.get(t, t)


def load_joined() -> pd.DataFrame:
    from wnba_oracle.db.reads import read_game_logs, read_label_corpus

    corpus = read_label_corpus().to_pandas()
    logs = read_game_logs().to_pandas()
    corpus = corpus.copy()
    corpus["initial"] = corpus["display_name"].map(lambda s: _norm(s)[:1])
    corpus["last"] = corpus["display_name"].map(
        lambda s: _norm(str(s).split()[-1]) if str(s).strip() else ""
    )
    corpus["talias"] = corpus["team"].map(alias)
    logs = logs.copy().rename(columns={"first_initial": "initial", "last_name": "last"})
    logs["talias"] = logs["team"].map(alias)
    logs = logs[logs["min"] > 0]

    # Primary join on (date, initial, last); disambiguate dup names by team.
    j = corpus.merge(
        logs[["game_date", "initial", "last", "talias", "min", "pts"]],
        left_on=["slate_date", "initial", "last"],
        right_on=["game_date", "initial", "last"],
        how="left",
        suffixes=("", "_log"),
    )
    # When a (date, initial, last) matched multiple log rows (dup names),
    # prefer the team-matching one.
    j["team_match"] = (j["talias"] == j["talias_log"]).fillna(False)
    j = j.sort_values("team_match", ascending=False).drop_duplicates(
        subset=["slate_date", "player_id"], keep="first"
    )
    return j


def main() -> None:
    j = load_joined()
    n_total = len(j)
    matched = j[j["min"].notna()].copy()
    print(
        f"corpus rows: {n_total}  |  matched to minutes: {len(matched)} "
        f"({len(matched) / n_total:.0%})"
    )
    cov26 = j[j["slate_date"] >= "2026-01-01"]
    cov26m = cov26[cov26["min"].notna()]
    print(
        f"2026 rows: {len(cov26)}  matched: {len(cov26m)} ({len(cov26m) / max(len(cov26), 1):.0%})"
    )
    matched["rate"] = matched["real_score"] / matched["min"].clip(lower=1.0)
    print(
        f"\nminutes: median {matched['min'].median():.1f}  "
        f"per-min rate: median {matched['rate'].median():.3f} "
        f"std-across-players {matched.groupby('player_id')['rate'].mean().std():.3f}"
    )

    # ---- Walk-forward player time series (EWMA of min and rate from PRIOR games) ----
    matched = matched.sort_values(["player_id", "slate_date"])
    HL = 3.0
    rows = []
    for pid, g in matched.groupby("player_id"):
        mins = g["min"].tolist()
        rates = g["rate"].tolist()
        reals = g["real_score"].tolist()
        boosts = g["card_boost"].tolist()
        dates = g["slate_date"].tolist()
        for i in range(len(g)):
            prior = list(range(i))[::-1]  # most-recent-first indices
            if not prior:
                continue
            w = np.array([0.5 ** (k / HL) for k in range(len(prior))])
            pm = float(np.dot(w, [mins[p] for p in prior]) / w.sum())
            pr = float(np.dot(w, [rates[p] for p in prior]) / w.sum())
            rows.append(
                {
                    "pid": pid,
                    "date": dates[i],
                    "n_prior": len(prior),
                    "real": reals[i],
                    "boost": boosts[i],
                    "proj_min": pm,
                    "proj_rate": pr,
                    "actual_min": mins[i],
                    "e_real_min": pm * pr,
                    "e_real_boost": boost_prior(boosts[i]),
                    # CEILING: if we knew tonight's minutes exactly but used the
                    # stable historical rate. Gap vs e_real_min = the value of a
                    # better minutes projection (the same-day-signal edge).
                    "e_real_perfectmin": mins[i] * pr,
                    "recent_real": float(np.dot(w, [reals[p] for p in prior]) / w.sum()),
                }
            )
    P = pd.DataFrame(rows)
    P26 = P[(P["date"] >= "2026-01-01") & (P["n_prior"] >= 3)]
    print(f"\nwalk-forward test rows (2026, >=3 prior games): {len(P26)}")

    def corr(a, b):
        return np.corrcoef(P26[a], P26[b])[0, 1]

    def mae(col):
        return float(np.mean(np.abs(P26["real"] - P26[col])))

    print("\n=== predicting next-game real_score (2026, walk-forward) ===")
    print(
        f"  corr(real, minutes x rate)  = {corr('real', 'e_real_min'):+.3f}   MAE {mae('e_real_min'):.3f}"
    )
    print(
        f"  corr(real, recent_real)     = {corr('real', 'recent_real'):+.3f}   MAE {mae('recent_real'):.3f}"
    )
    print(
        f"  corr(real, boost_prior)     = {corr('real', 'e_real_boost'):+.3f}   MAE {mae('e_real_boost'):.3f}"
    )
    print(f"  corr(real, proj_min alone)  = {corr('real', 'proj_min'):+.3f}")
    print(
        f"  corr(real, ACTUAL_min x rate)= {corr('real', 'e_real_perfectmin'):+.3f}   "
        f"MAE {mae('e_real_perfectmin'):.3f}   <- ceiling if minutes known"
    )
    print("  (minutes x rate must BEAT boost_prior to be a real edge. The")
    print("   actual-minutes row is the prize: the gap from proj to actual minutes")
    print("   is what same-day lineup/injury signals would close.)")

    # ---- per-slate ceiling-contribution ranking (what the optimizer ranks by) ----
    print("\n=== per-slate ranking quality (2026): top-5 recovers of realized top-8 ===")
    rec_min, rec_boost, rhos_min, rhos_boost = [], [], [], []
    for _d, g in P26.groupby("date"):
        if len(g) < 8:
            continue
        gg = g.merge(
            matched[["player_id", "slate_date", "card_boost"]],
            left_on=["pid", "date"],
            right_on=["player_id", "slate_date"],
            how="left",
        )
        b = gg["boost"].to_numpy()
        realized_cv = gg["real"].to_numpy() * (2.0 + b)
        min_cv = gg["e_real_min"].to_numpy() * (2.0 + b)
        boost_cv = gg["e_real_boost"].to_numpy() * (2.0 + b)
        top8 = set(np.argsort(realized_cv)[::-1][:8].tolist())
        rec_min.append(len(set(np.argsort(min_cv)[::-1][:5].tolist()) & top8))
        rec_boost.append(len(set(np.argsort(boost_cv)[::-1][:5].tolist()) & top8))
        rm = spearmanr(min_cv, realized_cv).correlation
        rb = spearmanr(boost_cv, realized_cv).correlation
        if not np.isnan(rm):
            rhos_min.append(rm)
        if not np.isnan(rb):
            rhos_boost.append(rb)
    print(
        f"  minutes x rate : recovery {np.mean(rec_min):.2f}/5   Spearman {np.mean(rhos_min):+.3f}"
    )
    print(
        f"  boost_prior    : recovery {np.mean(rec_boost):.2f}/5   Spearman {np.mean(rhos_boost):+.3f}"
    )


if __name__ == "__main__":
    main()
