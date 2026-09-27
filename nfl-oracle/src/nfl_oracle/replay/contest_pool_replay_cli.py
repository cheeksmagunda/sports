"""CLI: production pipeline replayed on each Corpus C contest's visible pool (#280).

Offline and read-only. Reads local Corpus G, local Corpus C, and one saved
nflverse ``ContextSnapshot``, and writes a JSON report. Never authenticates,
never enters a contest, never writes to the recommendation store.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nfl_oracle.contests.parse import iter_contests
from nfl_oracle.contests.store import ContestStore
from nfl_oracle.recommendations.optimizer import OptimizerConfig
from nfl_oracle.replay.contest_pool_replay import (
    ContestPool,
    replay_contest_pools,
    summarize,
)
from nfl_oracle.replay.production_backtest_cli import load_backtest_inputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfl-contest-pool-replay",
        description=(
            "Walk-forward replay of fit_model/predict/optimize on each finalized "
            "Corpus C contest's visible pool and boosts, against the same ceiling "
            "as the visible winner (observation only)."
        ),
    )
    parser.add_argument("--history-root", type=Path, default=Path("data/raw/corpus_g"))
    parser.add_argument("--contest-root", type=Path, default=Path("data/raw/corpus_c"))
    parser.add_argument(
        "--context-snapshot",
        type=Path,
        required=True,
        help="Saved nflverse ContextSnapshot JSON (as written by ContextSnapshot.save).",
    )
    parser.add_argument(
        "--retrain",
        choices=("week", "contest"),
        default="week",
        help="Retrain once per NFL (season, season_type, week) or once per contest.",
    )
    parser.add_argument("--simulations", type=int, default=100)
    parser.add_argument(
        "--full-samples",
        action="store_true",
        help="Keep full residual sample vectors in the optimizer (slow; same lineup).",
    )
    parser.add_argument("--out", type=Path, default=None, help="JSON report path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inputs = load_backtest_inputs(args.history_root, args.context_snapshot)
    contests = [
        contest
        for contest in iter_contests(ContestStore(args.contest_root), finalized_only=True)
        if contest.has_field_evidence
    ]
    week_of = inputs.week_of

    def fold_of(pool: ContestPool) -> Any:
        if args.retrain == "contest":
            return pool.contest_id
        return min(week_of[game_id] for game_id in pool.day_game_ids)

    def progress(line: str) -> None:
        print(line, file=sys.stderr, flush=True)

    started = datetime.now(UTC)
    results, excluded = replay_contest_pools(
        inputs.enriched,
        contests,
        fold_of=fold_of,
        team_keys=inputs.team_keys,
        optimizer_config=OptimizerConfig(simulations=args.simulations),
        compact_samples=not args.full_samples,
        progress=progress,
    )
    summary = summarize(results, excluded)
    payload = {
        "kind": "production_pipeline_contest_pool_replay",
        "issue": 280,
        "retrain": args.retrain,
        "contests_with_field_evidence": len(contests),
        "history_rows": len(inputs.rows),
        "history_excluded": inputs.history_excluded,
        "context_rows": inputs.context_rows,
        "context_excluded": inputs.context_excluded,
        "context_evidence_mode": inputs.context_evidence_mode,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "summary": asdict(summary),
        "contests": [{**asdict(result), "day": result.day.isoformat()} for result in results],
        "contest_entry": False,
    }
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(json.dumps({"summary": payload["summary"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
