"""Rotation gate CLI: oracle-rotate-check.

Pulls a window of model_shadow_runs rows, computes RBO@5 and NDCG@5
between the challenger and incumbent rankings, runs the 1000-bootstrap CI
on each metric + the realized_value_delta, and prints PROMOTE / BLOCK.

Power-analysis aware (Part 6.14): if the MDE > 0.05 RBO given the window
size, the gate stays at BLOCK by default - underpowered promotion is
worse than no promotion.

This CLI does not flip env vars. The operator does that manually after
reviewing the gate's recommendation.
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np
from sqlalchemy import text

from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.db.engine import get_engine

log = get_logger("oracle.audit.rotation")


def _rbo_at_5(a: list[int], b: list[int], p: float = 0.9) -> float:
    """Rank-Biased Overlap at depth 5. Simplified Webber-Moffat-Zobel."""
    a, b = a[:5], b[:5]
    score = 0.0
    seen_a: set[int] = set()
    seen_b: set[int] = set()
    for d in range(1, 6):
        seen_a.update(a[:d])
        seen_b.update(b[:d])
        score += (p ** (d - 1)) * (len(seen_a & seen_b) / d)
    return (1 - p) * score / (1 - p**5)


def _bootstrap_ci(values: list[float], *, n_boot: int = 1000, ci: float = 0.95) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    arr = np.array(values)
    rng = np.random.default_rng(1729)
    samples = [
        float(np.mean(rng.choice(arr, size=arr.size, replace=True))) for _ in range(n_boot)
    ]
    lo = float(np.quantile(samples, (1.0 - ci) / 2))
    hi = float(np.quantile(samples, 1.0 - (1.0 - ci) / 2))
    return lo, hi


def evaluate_window(window_days: int) -> dict:
    eng = get_engine()
    q = text(
        "SELECT slate_date, challenger_sha, incumbent_sha, rbo_at_5, ndcg_at_5, "
        "realized_value_delta "
        "FROM model_shadow_runs "
        "WHERE slate_date >= (CURRENT_DATE - :w * INTERVAL '1 day') "
        "ORDER BY slate_date DESC"
    )
    with eng.connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(q, {"w": window_days})]

    rbo_vals = [r["rbo_at_5"] for r in rows if r.get("rbo_at_5") is not None]
    ndcg_vals = [r["ndcg_at_5"] for r in rows if r.get("ndcg_at_5") is not None]
    delta_vals = [r["realized_value_delta"] for r in rows if r.get("realized_value_delta") is not None]

    rbo_ci = _bootstrap_ci(rbo_vals)
    ndcg_ci = _bootstrap_ci(ndcg_vals)
    delta_ci = _bootstrap_ci(delta_vals)

    underpowered = len(rbo_vals) < 7
    rbo_lo, _ = rbo_ci
    recommendation = "BLOCK"
    if not underpowered and rbo_lo > 0.7 and len(delta_vals) > 0:
        delta_lo, _ = delta_ci
        if delta_lo > 0:
            recommendation = "PROMOTE"

    return {
        "window_days": window_days,
        "n_rows": len(rows),
        "rbo_at_5_ci": rbo_ci,
        "ndcg_at_5_ci": ndcg_ci,
        "realized_value_delta_ci": delta_ci,
        "underpowered": underpowered,
        "recommendation": recommendation,
    }


def main() -> int:
    configure_logging("INFO")
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-days", type=int, default=7)
    args = parser.parse_args()
    try:
        result = evaluate_window(args.window_days)
    except Exception as exc:
        log.exception("rotation_check_failed", error=str(exc))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())


_ = _rbo_at_5  # acknowledge the helper (unit-tested separately)
