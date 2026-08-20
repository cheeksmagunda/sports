"""Calibrate STARTER_UNKNOWN_FADE and PICKER_BOOST_TAIL_LIFT from the corpus.

Reads-only against DATABASE_PUBLIC_URL. Joins slate_labels + job1_enrichment
across the full deployment window and reports:

  1. Starter-unknown fade multiplier for is_starter=0 & rotowire_confirmed=0
     against pred_p50 from the current model (MSE fit + ratio-of-means).
  2. Residual by card_boost tier: (realized_real_score - pred_p50) as a
     function of boost bin, to decide whether the boost tail is systematically
     under-predicted by the head.

Usage:
    scripts/with-secrets wnba-oracle -- uv run --package wnba-oracle \
      python scripts/calibrate_starter_and_boost.py

Outputs: a compact table on stdout; the recommended env-var values are
printed at the bottom.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Prod SHA -- calibrate against the model that will consume the knobs.
os.environ.setdefault(
    "WNBA_ORACLE_MODEL_ARTIFACT_SHA",
    "94f8e8606dab4d48652929bb3884fb9152e1abc766eeb2c2d86559f4318676cd",
)

sys.path.insert(0, str(_REPO_ROOT / "src"))

from sqlalchemy import text  # noqa: E402

from wnba_oracle.db.engine import get_engine  # noqa: E402
from wnba_oracle.scheduler.job2 import (  # noqa: E402
    _load_model_artifact,
    _predict_heads_for_pool,
)

BOOST_TIERS = [
    (0.0, 0.5, "boost_0.0-0.5"),
    (0.5, 1.0, "boost_0.5-1.0"),
    (1.0, 1.5, "boost_1.0-1.5"),
    (1.5, 2.0, "boost_1.5-2.0"),
    (2.0, 2.5, "boost_2.0-2.5"),
    (2.5, 10.0, "boost_2.5+"),
]


def _tier_for(boost: float) -> str:
    for lo, hi, name in BOOST_TIERS:
        if lo <= boost < hi:
            return name
    return "boost_unclassified"


def load_pool_rows() -> list[dict]:
    """Every (slate, pid) row from job1_enrichment joined with realized
    slate_labels. One row per player-slate. Skips slates with no labels."""
    eng = get_engine()
    q = text(
        """
        SELECT
          e.slate_date::text AS slate_date,
          e.player_id       AS pid,
          e.name            AS name,
          e.team            AS team,
          e.opponent        AS opponent,
          e.position        AS position,
          e.card_boost      AS enrich_boost,
          e.features_json   AS features_json,
          l.card_boost      AS label_boost,
          l.real_score      AS real_score
        FROM job1_enrichment e
        JOIN slate_labels l
          ON l.slate_date = e.slate_date::text
         AND l.platform_player_id = e.player_id
        WHERE l.real_score IS NOT NULL
        ORDER BY e.slate_date
        """
    )
    with eng.connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(q).fetchall()]
    return rows


def features_for(fj: object) -> dict:
    if not fj:
        return {}
    if isinstance(fj, str):
        try:
            return json.loads(fj)
        except json.JSONDecodeError:
            return {}
    return fj if isinstance(fj, dict) else {}


def predict_pool_p50_by_slate(
    rows_by_slate: dict[str, list[dict]],
) -> dict[tuple[str, int], dict[str, float]]:
    """Run the current model head over every historical pool. Returns
    {(slate_date, pid): {p10,p50,p90}} for pids the head produced."""
    sha = os.environ["WNBA_ORACLE_MODEL_ARTIFACT_SHA"]
    art = _load_model_artifact(sha)
    if art is None:
        raise SystemExit(f"model artifact {sha[:12]} not resolvable; run oracle-train?")
    out: dict[tuple[str, int], dict[str, float]] = {}
    for sd, rows in rows_by_slate.items():
        enrichment = [
            {
                "real_sports_player_id": r["pid"],
                "team": r["team"] or "",
                "opponent": r["opponent"] or "",
                "position": r["position"] or "F",
                "card_boost": float(r.get("label_boost") or r.get("enrich_boost") or 0.0),
                "features_json": r["features_json"],
            }
            for r in rows
        ]
        try:
            head = _predict_heads_for_pool(art, enrichment)
        except Exception as exc:
            print(f"[warn] {sd}: predict failed: {exc}", file=sys.stderr)
            continue
        for pid, qs in head.items():
            out[(sd, int(pid))] = qs
    return out


def fit_multiplier_mse(pairs: list[tuple[float, float]]) -> tuple[float, float]:
    """Analytic OLS multiplier m minimizing sum (real - pred*m)^2.
    Returns (m, mse_at_m). Empty input -> (1.0, 0.0)."""
    if not pairs:
        return 1.0, 0.0
    preds = np.array([p for p, _ in pairs], dtype=float)
    reals = np.array([r for _, r in pairs], dtype=float)
    denom = float(np.sum(preds * preds))
    if denom <= 1e-9:
        return 1.0, 0.0
    m = float(np.sum(preds * reals) / denom)
    resid = reals - preds * m
    return m, float(np.mean(resid * resid))


def main() -> int:
    print("Loading slate_labels + job1_enrichment...")
    rows = load_pool_rows()
    print(f"  {len(rows)} player-slate rows across {len({r['slate_date'] for r in rows})} slates\n")

    rows_by_slate: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        rows_by_slate[r["slate_date"]].append(r)

    print("Running current head against every historical pool (this takes ~2 min)...")
    p50_by_key = predict_pool_p50_by_slate(rows_by_slate)
    print(f"  {len(p50_by_key)} (slate, pid) head predictions produced\n")

    # ---- 1. Starter-unknown fade -----------------------------------------
    # Buckets: expected_starter (is_starter=1 OR rotowire_confirmed=1),
    # confirmed_bench (rotowire_confirmed=1 AND is_starter=0),
    # unknown (both flags 0), out (drop).
    buckets: dict[str, list[tuple[float, float, float]]] = defaultdict(
        list
    )  # (boost, pred_p50, real)
    for r in rows:
        key = (r["slate_date"], int(r["pid"]))
        pred = p50_by_key.get(key)
        if pred is None:
            continue
        f = features_for(r["features_json"])
        if int(f.get("is_out", 0) or 0):
            continue
        is_starter = int(f.get("is_starter", 0) or 0)
        rotowire_conf = int(f.get("rotowire_confirmed", 0) or 0)
        boost = float(r.get("label_boost") or r.get("enrich_boost") or 0.0)
        real = float(r["real_score"])
        p50 = float(pred["p50"])
        if is_starter == 0 and rotowire_conf == 0:
            bucket = "unknown"
        elif rotowire_conf == 1 and is_starter == 0:
            bucket = "confirmed_bench"
        else:
            bucket = "expected_starter"
        buckets[bucket].append((boost, p50, real))

    print(f"{'=' * 78}")
    print("STARTER FADE CALIBRATION")
    print(f"{'=' * 78}")
    print(
        f"{'bucket':<20}{'n':>8}{'mean_real':>12}{'mean_pred':>12}{'ratio':>8}"
        f"{'p_dnp':>8}{'p_bomb':>8}{'mse_m=1':>10}"
    )
    dnp_rate: dict[str, float] = {}
    for name in ("expected_starter", "confirmed_bench", "unknown"):
        rows_b = buckets.get(name, [])
        if not rows_b:
            continue
        n = len(rows_b)
        preds = np.array([p for _, p, _ in rows_b])
        reals = np.array([r for _, _, r in rows_b])
        mean_r = float(np.mean(reals))
        mean_p = float(np.mean(preds))
        ratio = mean_r / mean_p if mean_p > 1e-9 else 0.0
        p_dnp = float(np.mean(reals <= 0.01))
        p_bomb = float(np.mean(reals <= 1.0))
        mse1 = float(np.mean((reals - preds) ** 2))
        dnp_rate[name] = p_dnp
        print(
            f"{name:<20}{n:>8}{mean_r:>12.3f}{mean_p:>12.3f}{ratio:>8.3f}"
            f"{p_dnp:>8.2%}{p_bomb:>8.2%}{mse1:>10.3f}"
        )

    print()
    # Fade calibration only trusts slates where either flag is nonzero at all
    # (older enrichment predates the RotoWire wire-up; those rows land in the
    # "unknown" bucket by default and swamp the signal).
    slates_with_flags: set[str] = set()
    for r in rows:
        f = features_for(r["features_json"])
        if int(f.get("is_starter", 0) or 0) or int(f.get("rotowire_confirmed", 0) or 0):
            slates_with_flags.add(r["slate_date"])
    print(
        f"Restricting fade fit to {len(slates_with_flags)} slates that have "
        f"at least one player with a nonzero starter flag."
    )
    starter_pairs: list[tuple[float, float]] = []
    unknown_pairs: list[tuple[float, float]] = []
    for r in rows:
        key = (r["slate_date"], int(r["pid"]))
        pred = p50_by_key.get(key)
        if pred is None or r["slate_date"] not in slates_with_flags:
            continue
        f = features_for(r["features_json"])
        if int(f.get("is_out", 0) or 0):
            continue
        is_starter = int(f.get("is_starter", 0) or 0)
        rotowire_conf = int(f.get("rotowire_confirmed", 0) or 0)
        real = float(r["real_score"])
        p50 = float(pred["p50"])
        if is_starter == 0 and rotowire_conf == 0:
            unknown_pairs.append((p50, real))
        elif (is_starter == 1 or rotowire_conf == 1) and not (
            rotowire_conf == 1 and is_starter == 0
        ):
            starter_pairs.append((p50, real))
    print(f"  starters n={len(starter_pairs)}  unknowns n={len(unknown_pairs)}")
    if starter_pairs:
        preds = np.array([p for p, _ in starter_pairs])
        reals = np.array([r for _, r in starter_pairs])
        print(
            f"  starters: mean_real={np.mean(reals):.3f}  mean_pred={np.mean(preds):.3f}"
            f"  p_dnp={np.mean(reals <= 0.01):.2%}"
        )
    if unknown_pairs:
        preds = np.array([p for p, _ in unknown_pairs])
        reals = np.array([r for _, r in unknown_pairs])
        print(
            f"  unknowns: mean_real={np.mean(reals):.3f}  mean_pred={np.mean(preds):.3f}"
            f"  p_dnp={np.mean(reals <= 0.01):.2%}"
        )
    if unknown_pairs:
        m_unknown, mse_unknown = fit_multiplier_mse(unknown_pairs)
        # sweep m for reference
        best_m, best_mse = 1.0, float("inf")
        for cand in np.arange(0.3, 1.05, 0.05):
            preds = np.array([p for p, _ in unknown_pairs])
            reals = np.array([r for _, r in unknown_pairs])
            mse = float(np.mean((reals - preds * cand) ** 2))
            if mse < best_mse:
                best_m, best_mse = float(cand), mse
        print(f"unknowns: OLS m = {m_unknown:.3f} (MSE {mse_unknown:.3f})")
        print(
            f"unknowns: sweep min m in [0.30,1.00,step 0.05] -> {best_m:.2f} (MSE {best_mse:.3f})"
        )
    if unknown_pairs and starter_pairs:
        mean_ratio = float(np.mean([r for _, r in unknown_pairs])) / float(
            np.mean([r for _, r in starter_pairs])
        )
        # Existing starter mult is 1.10; so the "unknown mult vs starter mult" ratio implies
        # a starter mult-equivalent for unknowns of 1.10 * mean_ratio.
        print(f"ratio(mean_real unknown / mean_real starter) = {mean_ratio:.3f}")
        print(
            f"  implied fade vs current starter mult 1.10 -> unknown mult = {1.10 * mean_ratio:.3f}"
        )
    print()
    if unknown_pairs:
        print(
            "RECOMMENDATION: pick a fade between the OLS m and the ratio-of-means. "
            "Both should agree to within a few percent."
        )

    # ---- 2. Boost-tier residual ------------------------------------------
    print()
    print(f"{'=' * 78}")
    print("BOOST-TAIL RESIDUAL")
    print(f"{'=' * 78}")
    # residual = real - pred_p50, binned by boost tier, split by starter class
    tier_bucket: dict[str, list[tuple[float, float]]] = defaultdict(list)
    tier_bucket_starters: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for name in ("expected_starter", "unknown", "confirmed_bench"):
        for boost, p50, real in buckets.get(name, []):
            tier = _tier_for(boost)
            tier_bucket[tier].append((p50, real))
            if name == "expected_starter":
                tier_bucket_starters[tier].append((p50, real))

    print(f"{'tier':<20}{'n':>8}{'mean_real':>12}{'mean_pred':>12}{'resid':>10}{'ratio':>8}")
    tier_order = [name for _, _, name in BOOST_TIERS]
    for tier in tier_order:
        entries = tier_bucket.get(tier, [])
        if not entries:
            continue
        n = len(entries)
        preds = np.array([p for p, _ in entries])
        reals = np.array([r for _, r in entries])
        mean_r = float(np.mean(reals))
        mean_p = float(np.mean(preds))
        resid = mean_r - mean_p
        ratio = mean_r / mean_p if mean_p > 1e-9 else 0.0
        print(f"{tier:<20}{n:>8}{mean_r:>12.3f}{mean_p:>12.3f}{resid:>+10.3f}{ratio:>8.3f}")

    print()
    print("Starters-only (isolate the multiplier effect from the confirmed-bench fade):")
    print(f"{'tier':<20}{'n':>8}{'mean_real':>12}{'mean_pred':>12}{'resid':>10}{'ratio':>8}")
    for tier in tier_order:
        entries = tier_bucket_starters.get(tier, [])
        if not entries:
            continue
        n = len(entries)
        preds = np.array([p for p, _ in entries])
        reals = np.array([r for _, r in entries])
        mean_r = float(np.mean(reals))
        mean_p = float(np.mean(preds))
        resid = mean_r - mean_p
        ratio = mean_r / mean_p if mean_p > 1e-9 else 0.0
        print(f"{tier:<20}{n:>8}{mean_r:>12.3f}{mean_p:>12.3f}{resid:>+10.3f}{ratio:>8.3f}")

    print()
    # Decide the boost-tail knob from the starters-only residual: if the
    # residual is materially positive at boost>=2, the head systematically
    # under-predicts and we lift stage-1 filter for those pids to pred_p90.
    high_boost_entries: list[tuple[float, float]] = []
    for tier in ("boost_2.0-2.5", "boost_2.5+"):
        high_boost_entries.extend(tier_bucket.get(tier, []))
    if high_boost_entries:
        n = len(high_boost_entries)
        preds = np.array([p for p, _ in high_boost_entries])
        reals = np.array([r for _, r in high_boost_entries])
        resid = float(np.mean(reals - preds))
        ratio = float(np.mean(reals) / max(np.mean(preds), 1e-9))
        print(
            f"HIGH-BOOST (>=2.0): n={n} mean_real={np.mean(reals):.3f} "
            f"mean_pred={np.mean(preds):.3f} resid={resid:+.3f} ratio={ratio:.3f}"
        )
        if ratio >= 1.15:
            print("  -> ship PICKER_BOOST_TAIL_LIFT=true (stage-1 filter uses p90 for boost>=2)")
        else:
            print("  -> not materially under-predicted; keep PICKER_BOOST_TAIL_LIFT off")

    return 0


if __name__ == "__main__":
    sys.exit(main())
