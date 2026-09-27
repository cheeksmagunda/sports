"""Out-of-sample backtest graded on each slate's Highest value board (#505).

For each slate:
  1. Build enrichment from ``highestBoostedValuePlayers`` (card_boost visible
     pre-game); withhold real_score from the predictor (scoring ground truth).
  2. Run the job2 picker path under ``PAYOUT_REGIME=top_1`` /
     ``OPTIMIZER_OBJECTIVE_MODE=total_draft_value``.
  3. Score the committed lineup with realized real_scores.
  4. Grade against that slate's Highest value board (top-5 / top-10 players
     and HV hindsight score) — **not** prior users' winning drafts.

Winning-draft leaderboards are intentionally unused here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import polars as pl

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_SCRIPTS.parent / "src"))

from seasons_common import add_seasons_argument, in_seasons, parse_seasons  # noqa: E402

os.environ.setdefault(
    "WNBA_ORACLE_MODEL_ARTIFACT_SHA",
    "db18f6c9f495555e9df8f995e17679b93a7d26b1de77b39546d51ce2f5538f62",
)
os.environ.setdefault("CONTRARIAN_STRENGTH", "0.3")
os.environ.setdefault("CONTRARIAN_ENABLED", "true")
os.environ.setdefault("OPTIMIZER_MAX_PER_TEAM", "2")
os.environ.setdefault("PAYOUT_REGIME", "top_1")
os.environ.setdefault("OPTIMIZER_OBJECTIVE_MODE", "total_draft_value")

from wnba_oracle.eval.contest_score import committed_lineup_score  # noqa: E402
from wnba_oracle.eval.highest_value import (  # noqa: E402
    HV_SECTION,
    build_highest_value_reference,
    filter_highest_value_section,
    grade_lineup_vs_highest_value,
)
from wnba_oracle.picker.optimize import OptimizeConfig, optimize_lineup  # noqa: E402
from wnba_oracle.picker.payout import default_curve_for_regime  # noqa: E402
from wnba_oracle.scheduler.job2 import _build_specs  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_seasons_argument(parser)
    args = parser.parse_args(argv)
    seasons = parse_seasons(args.seasons)

    from wnba_oracle.db.reads import read_slate_labels

    sl_all = read_slate_labels()
    hv = filter_highest_value_section(sl_all)
    test_slates = sorted(
        d for d in hv["slate_date"].unique().to_list() if in_seasons(str(d), seasons)
    )
    print(f"Backtesting on {len(test_slates)} HV slates (seasons: {','.join(seasons)})")
    print(f"Reference section: {HV_SECTION}")
    print(f"Using artifact SHA: {os.environ['WNBA_ORACLE_MODEL_ARTIFACT_SHA'][:16]}...")
    print()

    rows: list[dict[str, object]] = []
    for sd in test_slates:
        reference = build_highest_value_reference(sl_all, str(sd))
        if reference is None:
            print(f"  {sd}  HV board too thin; skip")
            continue

        slate = hv.filter(pl.col("slate_date") == sd)
        teams = slate["team_key"].unique().to_list()
        team_to_opp = {t: teams[(i + 1) % len(teams)] for i, t in enumerate(teams)}

        enrichment = []
        boost_by_pid: dict[int, float] = {}
        rs_by_pid: dict[int, float] = {}
        for r in slate.iter_rows(named=True):
            pid = int(r["platform_player_id"])
            boost = float(r["card_boost"])
            rs = float(r["real_score"]) if r["real_score"] is not None else 0.0
            boost_by_pid[pid] = boost
            rs_by_pid[pid] = rs
            enrichment.append(
                {
                    "real_sports_player_id": str(pid),
                    "name": r["display_name"],
                    "team": r["team_key"],
                    "opponent": team_to_opp.get(r["team_key"], "UNK"),
                    "position": "F",
                    "card_boost": boost,
                    "features_json": json.dumps({}),
                }
            )

        samps, fields, _projection_by_pid = _build_specs(enrichment, slate_date=sd)
        if len(samps) < 5:
            print(f"  {sd}  pool too small ({len(samps)}); skip")
            continue
        cfg = OptimizeConfig(
            top_n_filter=min(20, len(samps)),
            n_samples=300,
            n_field_lineups=50,
            seed=2026,
            objective_mode="total_draft_value",
        )
        rec = optimize_lineup(samps, fields, default_curve_for_regime("top_1"), cfg=cfg)
        grade = grade_lineup_vs_highest_value(rec.player_ids, reference)
        our_score = committed_lineup_score(rec.player_ids, rs_by_pid, boost_by_pid)

        rows.append(
            {
                "slate_date": sd,
                "our_score": round(float(our_score), 2),
                "hv_top5_score": round(float(grade["hv_top5_score"]), 2),
                "hv_capture": round(float(grade["hv_capture_ratio"]), 3),
                "overlap_hv_top5": int(grade["overlap_hv_top5"]),
                "overlap_hv_top10": int(grade["overlap_hv_top10"]),
                "n_pool": len(samps),
                "hv_board_n": len(reference.players),
            }
        )

    if not rows:
        print("No graded slates.")
        return 1

    df = pl.DataFrame(rows)
    print()
    print("Per-slate results (graded vs Highest value board, not winning drafts):")
    with pl.Config(tbl_rows=40, tbl_cols=12, tbl_width_chars=140):
        print(df)

    print()
    print("=== Aggregate (HV reference) ===")
    print(f"Slates: {len(rows)}")
    print(f"Mean HV capture ratio: {np.mean([float(r['hv_capture']) for r in rows]):.3f}")
    print(f"Mean overlap HV top-5: {np.mean([int(r['overlap_hv_top5']) for r in rows]):.2f}/5")
    print(f"Mean overlap HV top-10: {np.mean([int(r['overlap_hv_top10']) for r in rows]):.2f}/5")
    print(
        f"Mean score gap vs HV top-5: "
        f"{np.mean([float(r['hv_top5_score']) - float(r['our_score']) for r in rows]):.2f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
