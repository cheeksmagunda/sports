"""CLI: walk-forward backtest of the production prediction pipeline (#280).

Offline and read-only. Reads the local Corpus G archive plus one saved nflverse
``ContextSnapshot`` (the same input ``_model_bundle`` enriches with), and
writes a JSON report. Never authenticates, never enters a contest, never
writes to the recommendation store.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nfl_oracle.recommendations.context import enrich_historical_rows
from nfl_oracle.recommendations.history import load_history, load_history_metadata
from nfl_oracle.recommendations.model import attach_enrichment
from nfl_oracle.recommendations.optimizer import OptimizerConfig
from nfl_oracle.recommendations.sources import ContextSnapshot
from nfl_oracle.replay.production_backtest import (
    backtest_production_pipeline,
    summarize,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfl-production-backtest",
        description=(
            "Walk-forward replay of fit_model/predict/optimize against finalized "
            "Corpus G outcomes; reports zero-boost capture ratio (observation only)."
        ),
    )
    parser.add_argument("--history-root", type=Path, default=Path("data/raw/corpus_g"))
    parser.add_argument(
        "--context-snapshot",
        type=Path,
        required=True,
        help="Saved nflverse ContextSnapshot JSON (as written by ContextSnapshot.save).",
    )
    parser.add_argument("--grouping", choices=("game", "day"), default="game")
    parser.add_argument(
        "--retrain",
        choices=("week", "slate"),
        default="week",
        help="Retrain once per NFL (season, season_type, week) or once per slate.",
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
    rows, history_excluded = load_history(args.history_root)
    metadata = load_history_metadata(args.history_root, rows)
    snapshot = ContextSnapshot.load(args.context_snapshot)
    enrichment = enrich_historical_rows(rows, snapshot, metadata=metadata)
    enriched = attach_enrichment(rows, enrichment)
    week_of = {
        game_id: (int(meta["season"]), str(meta["season_type"]), int(meta["week"]))
        for (_player, game_id), meta in metadata.items()
    }
    team_keys: dict[int, str] = {}
    for row in rows:
        meta = metadata[(row.player_id, row.game_id)]
        if row.team_id is not None:
            team_keys[row.team_id] = str(meta["team"])

    def fold_of(spec: Any) -> Any:
        if args.retrain == "slate":
            return spec.key
        return min(week_of[game_id] for game_id in spec.game_ids)

    def progress(line: str) -> None:
        print(line, file=sys.stderr, flush=True)

    started = datetime.now(UTC)
    results, excluded = backtest_production_pipeline(
        enriched,
        grouping=args.grouping,
        fold_of=fold_of,
        team_keys=team_keys,
        optimizer_config=OptimizerConfig(simulations=args.simulations),
        compact_samples=not args.full_samples,
        progress=progress,
    )
    summary = summarize(results, excluded)
    payload = {
        "kind": "production_pipeline_walk_forward_backtest",
        "issue": 280,
        "grouping": args.grouping,
        "retrain": args.retrain,
        "history_rows": len(rows),
        "history_excluded": history_excluded,
        "context_rows": len(enrichment.rows),
        "context_excluded": enrichment.excluded,
        "context_evidence_mode": enrichment.evidence_mode,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "summary": asdict(summary),
        "by_estimator": {
            name: sum(result.selected_estimator == name for result in results)
            for name in sorted({result.selected_estimator for result in results})
        },
        "slates": [{**asdict(result), "cutoff": result.cutoff.isoformat()} for result in results],
        "contest_entry": False,
    }
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(json.dumps({"summary": payload["summary"], "by_estimator": payload["by_estimator"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
