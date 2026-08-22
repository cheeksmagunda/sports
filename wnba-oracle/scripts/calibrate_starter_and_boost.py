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


def _group_rows_by_slate(rows: list[dict]) -> dict[str, list[dict]]:
    rows_by_slate: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        rows_by_slate[row["slate_date"]].append(row)
    return rows_by_slate


def _starter_bucket(features: dict) -> str:
    is_starter = int(features.get("is_starter", 0) or 0)
    rotowire_confirmed = int(features.get("rotowire_confirmed", 0) or 0)
    if is_starter == 0 and rotowire_confirmed == 0:
        return "unknown"
    if rotowire_confirmed == 1 and is_starter == 0:
        return "confirmed_bench"
    return "expected_starter"


def _build_starter_buckets(
    rows: list[dict],
    predictions: dict[tuple[str, int], dict[str, float]],
) -> dict[str, list[tuple[float, float, float]]]:
    buckets: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    for row in rows:
        key = (row["slate_date"], int(row["pid"]))
        pred = predictions.get(key)
        if pred is None:
            continue
        features = features_for(row["features_json"])
        if int(features.get("is_out", 0) or 0):
            continue
        boost = float(row.get("label_boost") or row.get("enrich_boost") or 0.0)
        real = float(row["real_score"])
        p50 = float(pred["p50"])
        buckets[_starter_bucket(features)].append((boost, p50, real))
    return buckets


def _print_starter_summary(buckets: dict[str, list[tuple[float, float, float]]]) -> None:
    print(f"{'=' * 78}")
    print("STARTER FADE CALIBRATION")
    print(f"{'=' * 78}")
    print(
        f"{'bucket':<20}{'n':>8}{'mean_real':>12}{'mean_pred':>12}{'ratio':>8}"
        f"{'p_dnp':>8}{'p_bomb':>8}{'mse_m=1':>10}"
    )
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
        print(
            f"{name:<20}{n:>8}{mean_r:>12.3f}{mean_p:>12.3f}{ratio:>8.3f}"
            f"{p_dnp:>8.2%}{p_bomb:>8.2%}{mse1:>10.3f}"
        )


def _slates_with_starter_flags(rows: list[dict]) -> set[str]:
    flagged: set[str] = set()
    for row in rows:
        features = features_for(row["features_json"])
        if int(features.get("is_starter", 0) or 0) or int(
            features.get("rotowire_confirmed", 0) or 0
        ):
            flagged.add(row["slate_date"])
    return flagged


def _fit_pairs(
    rows: list[dict],
    predictions: dict[tuple[str, int], dict[str, float]],
    flagged_slates: set[str],
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    starter_pairs: list[tuple[float, float]] = []
    unknown_pairs: list[tuple[float, float]] = []
    for row in rows:
        key = (row["slate_date"], int(row["pid"]))
        pred = predictions.get(key)
        if pred is None or row["slate_date"] not in flagged_slates:
            continue
        features = features_for(row["features_json"])
        if int(features.get("is_out", 0) or 0):
            continue
        pair = (float(pred["p50"]), float(row["real_score"]))
        bucket = _starter_bucket(features)
        if bucket == "unknown":
            unknown_pairs.append(pair)
        elif bucket == "expected_starter":
            starter_pairs.append(pair)
    return starter_pairs, unknown_pairs


def _print_pair_summary(name: str, pairs: list[tuple[float, float]]) -> None:
    if not pairs:
        return
    preds = np.array([pred for pred, _ in pairs])
    reals = np.array([real for _, real in pairs])
    print(
        f"  {name}: mean_real={np.mean(reals):.3f}  mean_pred={np.mean(preds):.3f}"
        f"  p_dnp={np.mean(reals <= 0.01):.2%}"
    )


def _print_fade_fit(
    starter_pairs: list[tuple[float, float]],
    unknown_pairs: list[tuple[float, float]],
) -> None:
    print(f"  starters n={len(starter_pairs)}  unknowns n={len(unknown_pairs)}")
    _print_pair_summary("starters", starter_pairs)
    _print_pair_summary("unknowns", unknown_pairs)

    if unknown_pairs:
        m_unknown, mse_unknown = fit_multiplier_mse(unknown_pairs)
        best_m, best_mse = 1.0, float("inf")
        preds = np.array([pred for pred, _ in unknown_pairs])
        reals = np.array([real for _, real in unknown_pairs])
        for candidate in np.arange(0.3, 1.05, 0.05):
            mse = float(np.mean((reals - preds * candidate) ** 2))
            if mse < best_mse:
                best_m, best_mse = float(candidate), mse
        print(f"unknowns: OLS m = {m_unknown:.3f} (MSE {mse_unknown:.3f})")
        print(
            f"unknowns: sweep min m in [0.30,1.00,step 0.05] -> {best_m:.2f} (MSE {best_mse:.3f})"
        )
    if unknown_pairs and starter_pairs:
        mean_ratio = float(np.mean([real for _, real in unknown_pairs])) / float(
            np.mean([real for _, real in starter_pairs])
        )
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


def _build_tier_buckets(
    starter_buckets: dict[str, list[tuple[float, float, float]]],
) -> tuple[
    dict[str, list[tuple[float, float]]],
    dict[str, list[tuple[float, float]]],
]:
    all_players: dict[str, list[tuple[float, float]]] = defaultdict(list)
    starters: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for name in ("expected_starter", "unknown", "confirmed_bench"):
        for boost, p50, real in starter_buckets.get(name, []):
            tier = _tier_for(boost)
            all_players[tier].append((p50, real))
            if name == "expected_starter":
                starters[tier].append((p50, real))
    return all_players, starters


def _print_tier_table(tier_buckets: dict[str, list[tuple[float, float]]]) -> None:
    print(f"{'tier':<20}{'n':>8}{'mean_real':>12}{'mean_pred':>12}{'resid':>10}{'ratio':>8}")
    for tier in (name for _, _, name in BOOST_TIERS):
        entries = tier_buckets.get(tier, [])
        if not entries:
            continue
        preds = np.array([pred for pred, _ in entries])
        reals = np.array([real for _, real in entries])
        mean_real = float(np.mean(reals))
        mean_pred = float(np.mean(preds))
        residual = mean_real - mean_pred
        ratio = mean_real / mean_pred if mean_pred > 1e-9 else 0.0
        print(
            f"{tier:<20}{len(entries):>8}{mean_real:>12.3f}{mean_pred:>12.3f}"
            f"{residual:>+10.3f}{ratio:>8.3f}"
        )


def _print_boost_tail_recommendation(
    tier_buckets: dict[str, list[tuple[float, float]]],
) -> None:
    high_boost_entries = [
        entry for tier in ("boost_2.0-2.5", "boost_2.5+") for entry in tier_buckets.get(tier, [])
    ]
    if not high_boost_entries:
        return
    preds = np.array([pred for pred, _ in high_boost_entries])
    reals = np.array([real for _, real in high_boost_entries])
    residual = float(np.mean(reals - preds))
    ratio = float(np.mean(reals) / max(np.mean(preds), 1e-9))
    print(
        f"HIGH-BOOST (>=2.0): n={len(high_boost_entries)} mean_real={np.mean(reals):.3f} "
        f"mean_pred={np.mean(preds):.3f} resid={residual:+.3f} ratio={ratio:.3f}"
    )
    if ratio >= 1.15:
        print("  -> ship PICKER_BOOST_TAIL_LIFT=true (stage-1 filter uses p90 for boost>=2)")
    else:
        print("  -> not materially under-predicted; keep PICKER_BOOST_TAIL_LIFT off")


def main() -> int:
    print("Loading slate_labels + job1_enrichment...")
    rows = load_pool_rows()
    print(f"  {len(rows)} player-slate rows across {len({r['slate_date'] for r in rows})} slates\n")

    print("Running current head against every historical pool (this takes ~2 min)...")
    predictions = predict_pool_p50_by_slate(_group_rows_by_slate(rows))
    print(f"  {len(predictions)} (slate, pid) head predictions produced\n")

    starter_buckets = _build_starter_buckets(rows, predictions)
    _print_starter_summary(starter_buckets)
    print()
    flagged_slates = _slates_with_starter_flags(rows)
    print(
        f"Restricting fade fit to {len(flagged_slates)} slates that have "
        f"at least one player with a nonzero starter flag."
    )
    starter_pairs, unknown_pairs = _fit_pairs(rows, predictions, flagged_slates)
    _print_fade_fit(starter_pairs, unknown_pairs)

    print()
    print(f"{'=' * 78}")
    print("BOOST-TAIL RESIDUAL")
    print(f"{'=' * 78}")
    tier_buckets, starter_tier_buckets = _build_tier_buckets(starter_buckets)
    _print_tier_table(tier_buckets)
    print()
    print("Starters-only (isolate the multiplier effect from the confirmed-bench fade):")
    _print_tier_table(starter_tier_buckets)
    print()
    _print_boost_tail_recommendation(tier_buckets)

    return 0


if __name__ == "__main__":
    sys.exit(main())
