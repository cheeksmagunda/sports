"""CLI: offline contest dry-run five-card shadow slate (hard-deny submit)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from nfl_oracle.strategy.dry_run import (
    build_offline_contest_dry_run,
    default_value_label_fixture_root,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfl-contest-dry-run",
        description=(
            "Offline contest dry-run: build a five-card shadow slate from "
            "value-label fixtures (observation_only / dry_run; never submits)."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help=(
            f"Corpus G / value-label fixture root (default: {default_value_label_fixture_root()})"
        ),
    )
    parser.add_argument(
        "--decision-season",
        type=int,
        default=None,
        help="Decision season for the shadow slate (default: latest in fixtures).",
    )
    parser.add_argument(
        "--feature-ridge",
        action="store_true",
        help="Opt into leakage-safe feature_ridge values (default: player/position priors).",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=1.0,
        help="Ridge alpha when --feature-ridge is set (default 1.0).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of ranked orderings to include (default 5).",
    )
    parser.add_argument(
        "--skip-submit-proof",
        action="store_true",
        help="Skip calling stub.submit() (still labels dry_run / contest_entry=false).",
    )
    parser.add_argument(
        "--include-schedule-slate",
        action="store_true",
        help="Attach offline schedule week slate (games/opponents; observation only).",
    )
    parser.add_argument(
        "--schedule-week",
        type=int,
        default=None,
        help="Schedule week when --include-schedule-slate (default: 1).",
    )
    parser.add_argument(
        "--schedule-date",
        type=str,
        default=None,
        help="ISO date YYYY-MM-DD for schedule slate resolution.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Optional data root for offline schedules.csv lookup.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit full JSON payload (default).",
    )
    parser.add_argument(
        "--text",
        action="store_true",
        help="Emit a short text summary instead of JSON.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root if args.root is not None else default_value_label_fixture_root()
    day = date.fromisoformat(args.schedule_date) if args.schedule_date else None
    try:
        payload = build_offline_contest_dry_run(
            corpus_root=root,
            decision_season=args.decision_season,
            use_feature_ridge=args.feature_ridge,
            alpha=args.alpha,
            top_k_orderings=max(1, args.top_k),
            prove_submit_denied=not args.skip_submit_proof,
            include_schedule_slate=args.include_schedule_slate,
            schedule_week=args.schedule_week,
            schedule_date=day,
            project_root=args.project_root,
        )
    except ValueError as exc:
        print(f"nfl-contest-dry-run error: {exc}", file=sys.stderr)
        return 2

    if args.text and not args.json:
        print("nfl-contest-dry-run (observation_only / dry_run; no contest entry)")
        print(f"mode={payload['mode']} dry_run={payload['dry_run']}")
        print(f"root={payload['corpus_root']}")
        print(f"decision_season={payload['decision_season']} game_id={payload['decision_game_id']}")
        print(f"value_source={payload['value_source']}")
        print(f"five_card_set={payload['five_card_set']}")
        best = payload["best_ordering"]
        print(f"best_ordering={best['player_ids']} total={best['total']}")
        proof = payload["submit_proof"]
        print(
            f"submit_denied={proof.get('submit_denied')} contest_entry={payload['contest_entry']}"
        )
        return 0

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
