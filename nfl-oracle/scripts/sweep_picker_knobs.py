#!/usr/bin/env python3
"""Sweep picker knobs on Corpus C contest-pool replay (shared weekly fits).

Observation only. Writes a JSON summary comparing capture ratios across
profiles. Does not change production defaults or Railway env.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from nfl_oracle.contests.parse import iter_contests
from nfl_oracle.contests.store import ContestStore
from nfl_oracle.recommendations.optimizer import OptimizerConfig
from nfl_oracle.recommendations.picker_knobs import PickerKnobs
from nfl_oracle.replay.contest_pool_replay import (
    ContestPool,
    replay_contest_pools_knob_sweep,
    summarize,
)
from nfl_oracle.replay.production_backtest_cli import load_backtest_inputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sweep-picker-knobs")
    parser.add_argument("--history-root", type=Path, default=Path("data/raw/corpus_g"))
    parser.add_argument("--contest-root", type=Path, default=Path("data/raw/corpus_c"))
    parser.add_argument("--context-snapshot", type=Path, required=True)
    parser.add_argument("--simulations", type=int, default=100)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    knobs_list = (
        PickerKnobs(profile="identity"),
        PickerKnobs(boost_rank_blend=0.25, profile="boost_0.25"),
        PickerKnobs(boost_rank_blend=0.50, profile="boost_0.50"),
        PickerKnobs(boost_rank_blend=0.75, profile="boost_0.75"),
        PickerKnobs(position_calibration=1.0, profile="pos_1.0"),
        PickerKnobs(boost_rank_blend=0.35, position_calibration=0.5, profile="boost_0.35_pos_0.5"),
    )
    inputs = load_backtest_inputs(args.history_root, args.context_snapshot)
    contests = [
        contest
        for contest in iter_contests(ContestStore(args.contest_root), finalized_only=True)
        if contest.has_field_evidence
    ]
    week_of = inputs.week_of

    def fold_of(pool: ContestPool):
        return min(week_of[game_id] for game_id in pool.day_game_ids)

    def progress(line: str) -> None:
        print(line, file=sys.stderr, flush=True)

    started = datetime.now(UTC)
    swept = replay_contest_pools_knob_sweep(
        inputs.enriched,
        contests,
        knobs_list,
        fold_of=fold_of,
        team_keys=inputs.team_keys,
        optimizer_config=OptimizerConfig(simulations=args.simulations),
        progress=progress,
    )
    finished = datetime.now(UTC)
    profiles = {}
    for profile, (results, excluded) in swept.items():
        summary = summarize(results, excluded)
        profiles[profile] = {
            "all": asdict(summary.all),
            "zero_boost": asdict(summary.zero_boost),
            "boosted": asdict(summary.boosted),
            "n_results": len(results),
            "excluded": dict(excluded),
        }
    payload = {
        "kind": "picker_knob_sweep",
        "issue": 280,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "profiles": profiles,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v["all"]["mean_capture_ratio"] for k, v in profiles.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
