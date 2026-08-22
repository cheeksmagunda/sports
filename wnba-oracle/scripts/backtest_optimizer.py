"""Run the picker on the 2026-05-25 slate using its actual realized
card_boost + real_score and see what lineup it would produce. Compare
to the actual winner (cpgooner = userId 7J6Olwav, score 40.60).

This is an *optimal hindsight* check using realized real_scores in place
of predictions. If the picker can't produce ~40 from realized values
there's a bug in the slot scheme / formula. With the corrected slot
multipliers [2.0, 1.8, 1.6, 1.4, 1.2] and additive (slot+boost) formula,
the upper bound is what a perfect oracle would pick.

Not a model evaluation — it tests the optimizer math, not the predictor.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import (
    DEFAULT_SLOT_MULTIPLIERS,
    OptimizeConfig,
    optimize_lineup,
)
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.sample import PlayerSamplingSpec

SLATE = "2026-05-25"


def main() -> int:
    from wnba_oracle.db.reads import read_leaderboards, read_slate_labels

    sl = read_slate_labels().filter(pl.col("slate_date") == SLATE)
    lb = read_leaderboards().filter(pl.col("slate_date") == SLATE)

    print(f"Slate {SLATE}: {sl.height} players, {lb.height} leaderboard entries")

    pool = [
        {
            "player_id": int(r["platform_player_id"]),
            "name": r["display_name"],
            "team": r["team_key"],
            "card_boost": float(r["card_boost"]),
            "real_score": float(r["real_score"] or 0.0),
        }
        for r in sl.iter_rows(named=True)
    ]
    # Filter to players with non-zero real_score (DNP players)
    pool = [p for p in pool if p["real_score"] != 0.0]
    print(f"Active pool (real_score != 0): {len(pool)}")

    # Build sampling specs using the REALIZED real_score as the predicted mean.
    # K=10 offset matches the optimizer's convention.
    K = 10.0
    sampling_specs = []
    field_specs = []
    for p in pool:
        rs = p["real_score"]
        mu = float(np.log(max(rs + K, 1.0)))
        sampling_specs.append(
            PlayerSamplingSpec(
                player_id=p["player_id"],
                team=p["team"],
                opponent="",  # unknown; correlation matrix degrades to identity
                mu=mu,
                sigma=0.01,  # tight (we know the value; this is hindsight)
                boost=p["card_boost"],
            )
        )
        field_specs.append(
            FieldPlayerSpec(
                player_id=p["player_id"],
                pred_real_score=rs,
                card_boost=p["card_boost"],
            )
        )

    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(
        top_n_filter=min(20, len(pool)),
        n_samples=300,
        n_field_lineups=50,
        seed=42,
    )
    rec = optimize_lineup(sampling_specs, field_specs, curve, cfg=cfg)

    name_by_id = {p["player_id"]: p["name"] for p in pool}
    boost_by_id = {p["player_id"]: p["card_boost"] for p in pool}
    rs_by_id = {p["player_id"]: p["real_score"] for p in pool}

    print()
    print("=== Optimizer pick (hindsight) ===")
    total = 0.0
    for pid, slot_mult in zip(rec.player_ids, DEFAULT_SLOT_MULTIPLIERS):
        nm = name_by_id.get(pid, f"pid={pid}")
        boost = boost_by_id.get(pid, 0)
        rs = rs_by_id.get(pid, 0)
        eff = slot_mult + boost
        pts = eff * rs
        total += pts
        print(
            f"  slot {slot_mult:.1f}x + boost {boost:.1f} = {eff:.1f}x * value {rs:.2f} = {pts:.2f}  ({nm})"
        )
    print(f"  TOTAL: {total:.2f}")
    print(f"  Optimizer expected_payout: {rec.expected_payout:.3f}")
    print(
        f"  p10/p50/p90: {rec.lineup_score_p10:.2f} / {rec.lineup_score_p50:.2f} / {rec.lineup_score_p90:.2f}"
    )

    print()
    print("=== Actual top-3 finishers for comparison ===")
    for r in lb.sort("rank").head(3).iter_rows(named=True):
        lineup = json.loads(r["lineup_json"])
        print(f"  rank {r['rank']:2d}  user={r['user_id']}  score={r['score']:.2f}")
        for p in lineup:
            print(
                f"      {p['displayName']:18s}  {p['multiplier']:.1f}x  value={float(p['value']):.2f}"
            )

    # Optimal possible: pick 5 highest (slot_mult + boost) * realized_score values via brute force.
    # Sort players by their "max contribution" (boost+2) * rs, then by next slot, etc.
    print()
    print("=== Brute force optimal (for sanity) ===")
    import itertools

    best_score = -np.inf
    best_combo = None
    for combo in itertools.combinations(range(len(pool)), 5):
        # rearrangement: sort combo by real_score desc, then assign slots
        members = sorted(combo, key=lambda i: -pool[i]["real_score"])
        s = 0.0
        for slot_idx, pidx in enumerate(members):
            p = pool[pidx]
            s += (DEFAULT_SLOT_MULTIPLIERS[slot_idx] + p["card_boost"]) * p["real_score"]
        if s > best_score:
            best_score = s
            best_combo = members
    print(f"  Best possible: {best_score:.2f}")
    for slot_idx, pidx in enumerate(best_combo):
        p = pool[pidx]
        eff = DEFAULT_SLOT_MULTIPLIERS[slot_idx] + p["card_boost"]
        print(
            f"    slot {DEFAULT_SLOT_MULTIPLIERS[slot_idx]:.1f}x  {p['name']:18s}  boost {p['card_boost']:.1f}  value {p['real_score']:.2f}  pts {eff * p['real_score']:.2f}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
