"""Walk-forward backtest: HONEST prediction-quality measurement (no leakage).

The EB artifact in scripts/backtest_counterfactual.py saw all 16 test slates,
so it cannot measure a prediction change. Here, for each 2026 test slate N we
build predictions using ONLY slates < N, exactly as the live path would on
that date. Compares predictors:

  boost_only  -- the calibrated boost handicap (D43), no player signal
  eb_wf       -- EB hierarchical baseline (career-mean shrinkage) refit on
                 slates < N each time
  form        -- the recency + boost-shrink predictor (predict/form.py, D52)

Two metrics:
  PART 1 (fast, no optimizer): per-slate Spearman(pred, realized ceil_contrib)
          and how many of the realized top-8 plays each predictor's top-5
          recovers. This isolates predictor quality.
  PART 2 (slow, runs the optimizer): full-pipeline placement vs the actual
          leaderboard, under the production optimizer (dynamic cap on,
          contrarian 0.2) with the new K=2 + per-player-sigma sampling.

Run:
  uv run python scripts/backtest_walkforward.py            # part 1 only
  uv run python scripts/backtest_walkforward.py --placement  # + part 2
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wnba_oracle.predict.form import (
    FormConfig,
    boost_prior,
    player_volatility,
    predict_real_scores,
)
from wnba_oracle.train.eb_baseline import EBHierarchicalBaseline

CORPUS = "data/processed/training_corpus.parquet"
LB_GLOB = "data/historical/leaderboards/**/data.parquet"


def prior_by_player(history: pd.DataFrame) -> dict[int, list[float]]:
    """{pid: [real_score most-recent-first]} from an as-of history slice."""
    h = history.sort_values("slate_date", ascending=False)
    out: dict[int, list[float]] = {}
    for pid, grp in h.groupby("player_id"):
        out[int(pid)] = grp["real_score"].tolist()
    return out


def eb_walkforward_pred(history: pd.DataFrame, pool: pd.DataFrame) -> dict[int, float]:
    """Fit EB on the as-of history, predict the pool. Cohort F for all (the
    corpus has no position split), so this is career-mean shrinkage."""
    if history.empty:
        return {int(r.player_id): boost_prior(r.card_boost) for r in pool.itertuples()}
    hp = pl.from_pandas(history[["player_id", "real_score"]].assign(cohort="F"))
    eb = EBHierarchicalBaseline()
    eb.fit(hp, target="real_score", cohort_col="cohort", player_col="player_id")
    mu = eb.cohort_means.get("F", float(history["real_score"].mean()))
    out = {}
    for r in pool.itertuples():
        alpha = eb.player_alpha.get(int(r.player_id))
        out[int(r.player_id)] = max(0.5, mu + alpha) if alpha is not None else boost_prior(r.card_boost)
    return out


def predictor_quality(corpus: pd.DataFrame, slates: list[str]) -> None:
    print("=" * 74)
    print("PART 1: PREDICTOR QUALITY (walk-forward, no leakage, no optimizer)")
    print("=" * 74)
    cfg = FormConfig()
    rows = {k: {"rho": [], "recov": []} for k in ("boost_only", "eb_wf", "form")}
    for sd in slates:
        history = corpus[corpus["slate_date"] < sd]
        pool = corpus[corpus["slate_date"] == sd].drop_duplicates("player_id")
        if len(pool) < 6:
            continue
        boost_by = {int(r.player_id): float(r.card_boost) for r in pool.itertuples()}
        prior = prior_by_player(history)
        realized = np.array([r.real_score * (2.0 + r.card_boost) for r in pool.itertuples()])
        top8 = set(np.argsort(realized)[::-1][:8].tolist())
        preds = {
            "boost_only": {p: boost_prior(b) for p, b in boost_by.items()},
            "eb_wf": eb_walkforward_pred(history, pool),
            "form": predict_real_scores(prior, boost_by, cfg=cfg),
        }
        pids = [int(r.player_id) for r in pool.itertuples()]
        boosts = [float(r.card_boost) for r in pool.itertuples()]
        for name, pred in preds.items():
            cv = np.array([pred[p] * (2.0 + b) for p, b in zip(pids, boosts)])
            rho = spearmanr(cv, realized).correlation
            if not np.isnan(rho):
                rows[name]["rho"].append(rho)
            pred_top5 = set(np.argsort(cv)[::-1][:5].tolist())
            rows[name]["recov"].append(len(pred_top5 & top8))
    print(f"  {'predictor':12s} {'mean Spearman':>14s} {'top-5 recovers of top-8':>26s}")
    for name in ("boost_only", "eb_wf", "form"):
        print(f"  {name:12s} {np.mean(rows[name]['rho']):>+14.3f} "
              f"{np.mean(rows[name]['recov']):>22.2f}/5")
    print("\n  (boost_only is the no-player-signal floor; eb_wf is the honest"
          " version of\n   today's model; form should beat both if recency helps.)")


def _load_drafts_by_slate() -> dict[str, dict[int, int]]:
    sl = pl.read_parquet("data/historical/slate_labels/**/data.parquet")
    out: dict[str, dict[int, int]] = {}
    for r in sl.iter_rows(named=True):
        if r.get("drafts") is None:
            continue
        out.setdefault(str(r["slate_date"]), {})[int(r["platform_player_id"])] = int(r["drafts"])
    return out


def run_placement(corpus: pd.DataFrame, lb: pl.DataFrame, slates: list[str]) -> None:
    """PART 2: end-to-end placement walk-forward. Isolates predictor and
    sampling calibration; cap=dynamic and contrarian=0.2 held constant."""
    import json as _json

    from wnba_oracle.picker.field import FieldPlayerSpec
    from wnba_oracle.picker.optimize import OptimizeConfig, optimize_lineup
    from wnba_oracle.picker.payout import default_curve_for_regime
    from wnba_oracle.picker.popularity import (
        ContrarianConfig,
        apply_contrarian_adjustment,
        slate_labels_to_popularity,
    )
    from wnba_oracle.picker.sample import PlayerSamplingSpec

    print("\n" + "=" * 74)
    print("PART 2: PLACEMENT (walk-forward, full optimizer; deltas are the signal)")
    print("=" * 74)
    drafts_by_slate = _load_drafts_by_slate()
    curve = default_curve_for_regime("top_20")
    cc = ContrarianConfig(enabled=True, strength=0.2)

    def build_and_score(sd, pool, prior, preds, *, K, per_player_sigma):
        boost_by = {int(r.player_id): float(r.card_boost) for r in pool.itertuples()}
        pop = slate_labels_to_popularity(drafts_by_slate.get(sd, {}))
        adj = apply_contrarian_adjustment(preds, pop, cc)
        vol = player_volatility(prior)
        samps, fields = [], []
        teams = pool["team"].unique().tolist()
        opp = {t: teams[(i + 1) % len(teams)] for i, t in enumerate(teams)}
        for r in pool.itertuples():
            pid = int(r.player_id)
            pred = max(0.5, adj[pid])
            mu = float(np.log(max(pred + K, 1.0)))
            sigma = (
                min(0.6, max(0.12, vol.get(pid, 1.17) / max(pred + K, 1e-6)))
                if per_player_sigma else 0.25
            )
            samps.append(PlayerSamplingSpec(pid, str(r.team), str(opp.get(r.team, "")), mu, sigma, float(r.card_boost)))
            fields.append(FieldPlayerSpec(pid, pred, float(r.card_boost)))
        cfg = OptimizeConfig(
            top_n_filter=min(18, len(samps)), n_samples=200, n_field_lineups=40,
            seed=2026, max_per_team=2, dynamic_team_cap=True, score_offset=K,
        )
        rec = optimize_lineup(samps, fields, curve, cfg=cfg)
        rs_by = {int(r.player_id): float(r.real_score) for r in pool.itertuples()}
        members = sorted(((p, rs_by.get(int(p), 0.0)) for p in rec.player_ids), key=lambda x: -x[1])
        slots = [2.0, 1.8, 1.6, 1.4, 1.2]
        our = sum((slots[i] + boost_by.get(int(p), 0.0)) * rs for i, (p, rs) in enumerate(members))
        lb_s = lb.filter(pl.col("slate_date") == sd).sort("rank")
        scores = sorted(lb_s["score"].to_list(), reverse=True)
        placement = sum(1 for s in scores if s >= our) + 1
        win = {int(p["playerId"]) for p in _json.loads(lb_s.row(0, named=True)["lineup_json"])}
        return placement, our, scores[0], len({int(p) for p in rec.player_ids} & win)

    configs = {
        "P0 eb_wf  + old(K10,flat)": ("eb", 10.0, False),
        "P1 boost  + old(K10,flat)": ("boost", 10.0, False),
        "P2 boost  + new(K2,sigma)": ("boost", 2.0, True),
        "P3 eb_wf  + new(K2,sigma)": ("eb", 2.0, True),
    }
    results = {k: [] for k in configs}
    for sd in slates:
        history = corpus[corpus["slate_date"] < sd]
        pool = corpus[corpus["slate_date"] == sd].drop_duplicates("player_id")
        if len(pool) < 6:
            continue
        prior = prior_by_player(history)
        boost_by = {int(r.player_id): float(r.card_boost) for r in pool.itertuples()}
        preds = {
            "boost": {p: boost_prior(b) for p, b in boost_by.items()},
            "eb": eb_walkforward_pred(history, pool),
        }
        for name, (pname, K, pps) in configs.items():
            placement, our, top1, ov = build_and_score(sd, pool, prior, preds[pname], K=K, per_player_sigma=pps)
            results[name].append({"placement": placement, "our": our, "top1": top1, "overlap": ov})
    print(f"  {'config':28s} {'top20':>6s} {'top5':>5s} {'top1':>5s} {'mean_gap':>9s} {'overlap':>8s}")
    for name, rows in results.items():
        n = len(rows)
        t20 = sum(1 for r in rows if r["placement"] <= 20)
        t5 = sum(1 for r in rows if r["placement"] <= 5)
        t1 = sum(1 for r in rows if r["placement"] == 1)
        gap = np.mean([r["top1"] - r["our"] for r in rows])
        ov = np.mean([r["overlap"] for r in rows])
        print(f"  {name:28s} {t20:>4d}/{n} {t5:>5d} {t1:>5d} {gap:>9.2f} {ov:>6.2f}/5")


def main() -> int:
    corpus = pd.read_parquet(CORPUS)
    lb = pl.read_parquet(LB_GLOB)
    slates = sorted(d for d in corpus["slate_date"].unique() if str(d).startswith("2026-"))
    print(f"Walk-forward over {len(slates)} 2026 slates "
          f"(history grows from {corpus['slate_date'].min()})\n")
    predictor_quality(corpus, slates)

    if "--placement" in sys.argv:
        run_placement(corpus, lb, slates)
    return 0


if __name__ == "__main__":
    sys.exit(main())
