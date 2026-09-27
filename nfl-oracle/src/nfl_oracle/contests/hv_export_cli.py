"""``nfl-corpus-c-hv-export`` — offline Corpus C → Total Value / HV board export.

Walks on-disk Corpus C (``NFL_CORPUS_C_ROOT`` or ``data/raw/corpus_c`` under the
project / Railway volume at ``/app/nfl-oracle/data``). Writes per-contest
``total_value_leaderboard.json``, ``draft_stats_all_sections.jsonl``,
``matchups.json``, plus ``coverage_manifest.json`` gaps.

Read-only. No Real Sports network calls. No contest entry. No credential minting.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nfl_oracle.contests.hv_export import (
    export_corpus_c,
    resolve_corpus_c_root,
    resolve_export_root,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfl-corpus-c-hv-export",
        description=(
            "Export Corpus C draft_stats Total Value boards to durable JSON/JSONL "
            "(offline; empty volume scaffolds coverage_manifest gaps)."
        ),
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=None,
        help="Corpus C root (default NFL_CORPUS_C_ROOT or data/raw/corpus_c)",
    )
    parser.add_argument(
        "--export-root",
        type=Path,
        default=None,
        help="Export destination (default NFL_HV_EXPORT_ROOT or data/export/hv_boards)",
    )
    parser.add_argument(
        "--contest-id",
        type=int,
        action="append",
        default=None,
        help="Limit to one or more contest ids (repeatable)",
    )
    parser.add_argument("--json", action="store_true", help="print summary JSON to stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    corpus = resolve_corpus_c_root(args.corpus_root)
    export_root = resolve_export_root(args.export_root)
    summary = export_corpus_c(
        corpus_root=corpus,
        export_root=export_root,
        contest_ids=args.contest_id,
    )
    if args.json:
        print(json.dumps(summary.to_dict(), sort_keys=True))
    else:
        print(
            f"corpus_c={summary.corpus_c_root} export={summary.export_root} "
            f"seen={summary.contests_seen} exported={summary.contests_exported} "
            f"partial={summary.contests_partial} gaps={len(summary.gaps)} "
            f"volume_empty={summary.volume_empty}",
            file=sys.stderr,
        )
        print(f"coverage_manifest={export_root / 'coverage_manifest.json'}", file=sys.stderr)
    # Empty volume is an expected Codespace/Railway state — scaffold succeeds.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
