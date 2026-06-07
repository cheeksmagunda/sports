"""R9 refinement: empirically calibrate AvailabilityConfig.

The two-part availability model (predict/availability.py, D59) shrinks
cold-start dart projections toward zero so the optimizer cannot ship
boost-3 rookies with no minutes history. The original config values
(prior_active=0.30, neutral_prior=0.60) were design guesses. This
script measures empirical P(min >= 10) by recent-L5 minutes bucket over
the gamelog corpus and recommends recalibrated defaults.

Output: console table and a JSON snapshot at
  research/internal/_availability_calibration.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import polars as pl
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from wnba_oracle.common.db_utils import normalize_postgres_url  # noqa: E402
from wnba_oracle.db.reads import read_game_logs  # noqa: E402
from wnba_oracle.features.corpus import build_gamelog_corpus  # noqa: E402


def _engine() -> sa.Engine:
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")
    if not url:
        raise RuntimeError("set DATABASE_URL or DATABASE_PUBLIC_URL")
    return sa.create_engine(normalize_postgres_url(url), future=True, pool_pre_ping=True)


def main() -> int:
    eng = _engine()
    gl = read_game_logs(engine=eng)
    corpus = build_gamelog_corpus(gl, min_prior_games=1)
    print(f"game_logs={len(gl)} corpus={len(corpus)}")
    corp = corpus.filter(
        pl.col("mins_l5").is_not_null() & pl.col("minutes_played").is_not_null()
    )

    bins = [(0, 5), (5, 15), (15, 25), (25, 99)]
    rows: list[dict] = []
    print()
    print(f"  {'bin':<12} {'n':>6} {'P(min>=10)':>12} {'mean_min':>10}")
    for lo, hi in bins:
        sub = corp.filter((pl.col("mins_l5") >= lo) & (pl.col("mins_l5") < hi))
        n = len(sub)
        p_active = float((sub.get_column("minutes_played") >= 10).mean() or 0.0)
        mean_min = float(sub.get_column("minutes_played").mean() or 0.0)
        label = f"[{lo}, {hi})"
        print(f"  {label:<12} {n:>6} {p_active:>12.3f} {mean_min:>10.1f}")
        rows.append(
            {"bin_lo": lo, "bin_hi": hi, "n": n, "p_active": p_active, "mean_min": mean_min}
        )

    # No-history rows: corpus filter drops them; report 0 explicitly so the
    # snapshot still reads cleanly when the upstream filter changes.
    no_history = corpus.filter(
        pl.col("mins_l5").is_null() & pl.col("minutes_played").is_not_null()
    )
    print(
        f"  no-history (mins_l5 IS NULL): n={len(no_history)} "
        "(corpus filter drops them; no-history is a serve-time concept, "
        "not a corpus row)"
    )

    # Recommendation rule:
    #   prior_active   <- P(min>=10) of the [0,5) bucket (cold/bench rate)
    #   neutral_prior  <- P(min>=10) of the [5,15) bucket (rotation-bench rate,
    #                                                       the shrinkage target
    #                                                       for any-history)
    rec = {
        "prior_active": next(r["p_active"] for r in rows if r["bin_lo"] == 0),
        "neutral_prior": next(r["p_active"] for r in rows if r["bin_lo"] == 5),
    }
    print()
    print("  recommended AvailabilityConfig:")
    print(f"    prior_active  = {rec['prior_active']:.3f}  (cold/bench bucket rate)")
    print(f"    neutral_prior = {rec['neutral_prior']:.3f}  (rotation-bench bucket rate)")

    out = ROOT / "research" / "internal" / "_availability_calibration.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"bins": rows, "recommended": rec}, indent=2))
    print(f"\n  JSON: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
