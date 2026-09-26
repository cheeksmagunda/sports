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
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nfl_oracle.recommendations.context import enrich_historical_rows
from nfl_oracle.recommendations.history import load_history, load_history_metadata
from nfl_oracle.recommendations.model import FitConfig, HistoricalPerformance, attach_enrichment
from nfl_oracle.recommendations.optimizer import OptimizerConfig
from nfl_oracle.recommendations.sources import ContextSnapshot
from nfl_oracle.replay.production_backtest import (
    backtest_production_pipeline,
    summarize,
)


@dataclass(frozen=True)
class BacktestInputs:
    """Corpus G rows enriched exactly as ``_model_bundle`` does, plus join keys."""

    rows: tuple[HistoricalPerformance, ...]
    enriched: tuple[HistoricalPerformance, ...]
    history_excluded: dict[str, int]
    context_rows: int
    context_excluded: dict[str, int]
    context_evidence_mode: str
    week_of: dict[int, tuple[int, str, int]]
    team_keys: dict[int, str]


def load_backtest_inputs(history_root: Path, context_snapshot: Path) -> BacktestInputs:
    rows, history_excluded = load_history(history_root)
    metadata = load_history_metadata(history_root, rows)
    snapshot = ContextSnapshot.load(context_snapshot)
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
    return BacktestInputs(
        rows=tuple(rows),
        enriched=tuple(enriched),
        history_excluded=dict(history_excluded),
        context_rows=len(enrichment.rows),
        context_excluded=enrichment.excluded,
        context_evidence_mode=enrichment.evidence_mode,
        week_of=week_of,
        team_keys=team_keys,
    )


def add_fit_config_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--fit-ridge-alpha", type=float, default=10.0)
    parser.add_argument("--fit-holdout-fraction", type=float, default=0.8)
    parser.add_argument("--fit-min-train-kickoffs", type=int, default=2)
    parser.add_argument("--fit-min-unique-kickoffs", type=int, default=5)
    parser.add_argument("--fit-min-training-rows", type=int, default=30)
    parser.add_argument("--fit-min-design-rows", type=int, default=10)


def fit_config_from_args(args: argparse.Namespace) -> FitConfig:
    return FitConfig(
        ridge_alpha=args.fit_ridge_alpha,
        holdout_fraction=args.fit_holdout_fraction,
        min_train_kickoffs=args.fit_min_train_kickoffs,
        min_unique_kickoffs=args.fit_min_unique_kickoffs,
        min_training_rows=args.fit_min_training_rows,
        min_design_rows=args.fit_min_design_rows,
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
    add_fit_config_args(parser)
    parser.add_argument("--out", type=Path, default=None, help="JSON report path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inputs = load_backtest_inputs(args.history_root, args.context_snapshot)
    week_of = inputs.week_of

    def fold_of(spec: Any) -> Any:
        if args.retrain == "slate":
            return spec.key
        return min(week_of[game_id] for game_id in spec.game_ids)

    def progress(line: str) -> None:
        print(line, file=sys.stderr, flush=True)

    started = datetime.now(UTC)
    fit_config = fit_config_from_args(args)
    results, excluded = backtest_production_pipeline(
        inputs.enriched,
        grouping=args.grouping,
        fold_of=fold_of,
        team_keys=inputs.team_keys,
        optimizer_config=OptimizerConfig(simulations=args.simulations),
        fit_config=fit_config,
        compact_samples=not args.full_samples,
        progress=progress,
    )
    summary = summarize(results, excluded)
    payload = {
        "kind": "production_pipeline_walk_forward_backtest",
        "issue": 280,
        "grouping": args.grouping,
        "retrain": args.retrain,
        "fit_config": fit_config.model_dump(mode="json"),
        "history_rows": len(inputs.rows),
        "history_excluded": inputs.history_excluded,
        "context_rows": inputs.context_rows,
        "context_excluded": inputs.context_excluded,
        "context_evidence_mode": inputs.context_evidence_mode,
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
