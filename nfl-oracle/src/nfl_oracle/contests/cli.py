"""``nfl-contest-backfill`` — resumable, read-only Corpus C collection.

This command only ever issues GET requests against the contest read family. It
has no code path that can enter, edit, or submit a lineup.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx

from nfl_oracle.contests.collector import ContestOutcome, ContestScanner, scan_range
from nfl_oracle.contests.store import ContestStore, ScanCursor, cursor_path
from nfl_oracle.ingest.realsports import capture_live_headers, headers_or_capture


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfl-contest-backfill",
        description="Read-only sweep of the Real Sports contest id space (no entry).",
    )
    parser.add_argument("--start", type=int, default=1, help="lowest contest id to examine")
    parser.add_argument("--end", type=int, required=True, help="highest contest id to examine")
    parser.add_argument("--sport", default="nfl", help="sport to descend into (default nfl)")
    parser.add_argument("--descending", action="store_true", help="walk newest ids first")
    parser.add_argument("--retry-failed", action="store_true", help="re-examine failed ids")
    parser.add_argument("--max-requests", type=int, default=None, help="hard request ceiling")
    parser.add_argument("--pause", type=float, default=0.05, help="seconds between requests")
    parser.add_argument("--root", type=Path, default=None, help="corpus_c root override")
    parser.add_argument("--cursor", type=Path, default=None, help="cursor file override")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable summary")
    parser.add_argument("--quiet", action="store_true", help="suppress per-contest progress")
    return parser


async def _run(args: argparse.Namespace) -> int:
    if args.end < args.start:
        print("invalid_range", file=sys.stderr)
        return 2
    store = ContestStore(args.root)
    cursor_file = args.cursor or cursor_path()
    cursor = ScanCursor.load(cursor_file)
    ids = list(range(args.start, args.end + 1))
    if args.descending:
        ids.reverse()
    pending = cursor.pending(ids, retry_failed=args.retry_failed)
    if not args.quiet:
        print(
            f"corpus_c scan sport={args.sport} range={args.start}-{args.end} "
            f"pending={len(pending)} already_resolved={len(ids) - len(pending)}",
            file=sys.stderr,
        )

    found: list[ContestOutcome] = []

    def report(outcome: ContestOutcome) -> None:
        if outcome.kind == "nfl":
            found.append(outcome)
        if args.quiet:
            return
        if outcome.kind in {"nfl", "failed"}:
            print(
                f"  {outcome.contest_id}: {outcome.kind} sport={outcome.sport} "
                f"day={outcome.day} finalized={outcome.is_finalized} "
                f"entrants={outcome.entrants} detail={outcome.detail}",
                file=sys.stderr,
            )

    headers = await headers_or_capture()
    async with httpx.AsyncClient(timeout=30) as client:
        scanner = ContestScanner(
            client,
            headers,
            store,
            refresh_headers=capture_live_headers,
            request_pause_s=args.pause,
        )
        outcomes = await scan_range(
            scanner,
            pending,
            cursor,
            cursor_file,
            sport=args.sport,
            on_outcome=report,
            max_requests=args.max_requests,
        )

    summary = {
        "status": "complete" if len(outcomes) == len(pending) else "partial",
        "sport": args.sport,
        "range": [args.start, args.end],
        "examined": len(outcomes),
        "requests": scanner.requests,
        "nfl_found": len(found),
        "nfl_finalized": sum(1 for o in found if o.is_finalized),
        "other_sport": sum(1 for o in outcomes if o.kind == "other_sport"),
        "absent": sum(1 for o in outcomes if o.kind == "absent"),
        "failed": sum(1 for o in outcomes if o.kind == "failed"),
        "total_nfl_in_corpus": len(cursor.nfl_collected),
        "cursor": str(cursor_file),
        "finished_at": datetime.now(UTC).isoformat(),
        "contest_entry": False,
    }
    print(json.dumps(summary, indent=None if args.json else 2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
