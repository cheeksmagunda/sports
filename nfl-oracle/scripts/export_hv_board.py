"""NFL HV board export scaffold (issue #526).

Corpus C ``draftStats`` / ``highestBoostedValuePlayers`` maps through
``nfl_oracle.contests.parse.parse_draft_stats``. Durable append uses
``oracle_core.hv_board_corpus``.

This entry point is fail-closed without a finalized contest stats JSON path
or live auth wiring. Live one-slate NFL proof is a follow-on once Corpus C
dayclose embeds are chosen as the source of truth for a given slate.

Usage::

    uv run --frozen --package nfl-oracle python nfl-oracle/scripts/export_hv_board.py \\
      --corpus-root /tmp/sports-realsports-corpus --stats-json /path/to/stats.json \\
      --contest-id 2124 --slate-date 2025-09-14
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from oracle_core.hv_board_corpus import HvBoardPlayer, append_hv_board, build_hv_board

from nfl_oracle.contests.parse import parse_draft_stats


def _players_from_stats(stats_payload: dict, *, contest_id: int) -> list[HvBoardPlayer]:
    rows = parse_draft_stats(stats_payload, contest_id=contest_id)
    out: list[HvBoardPlayer] = []
    for row in rows:
        if row.section != "highestBoostedValuePlayers":
            continue
        out.append(
            HvBoardPlayer(
                player_id=int(row.player_id),
                name=str(row.display_name or ""),
                team=str(row.team_id) if row.team_id is not None else "",
                real_score=row.avg_score,
                base=row.base_boosted_value,
                card_boost=float(row.card_boost),
                slot=row.most_common_slot,
                drafts=row.draft_count,
                value=row.value,
            )
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--stats-json", type=Path, default=None)
    parser.add_argument("--contest-id", type=int, required=True)
    parser.add_argument("--slate-date", type=str, required=True)
    args = parser.parse_args(argv)

    if args.stats_json is None or not args.stats_json.is_file():
        print(
            "export_hv_board: FAIL_CLOSED need --stats-json with finalized "
            "contest /stats payload (live NFL scrape not wired in this scaffold). "
            "Refs #526.",
            file=sys.stderr,
        )
        return 78

    payload = json.loads(args.stats_json.read_text(encoding="utf-8"))
    players = _players_from_stats(payload, contest_id=args.contest_id)
    if not players:
        print(
            "export_hv_board: no highestBoostedValuePlayers rows in stats payload",
            file=sys.stderr,
        )
        return 1

    doc = build_hv_board(
        sport="nfl",
        slate_date=args.slate_date,
        contest_id=args.contest_id,
        players=players,
    )
    summary = append_hv_board(doc, args.corpus_root)
    print(
        "export_hv_board: ok "
        f"sport={summary['sport']} slate={summary['slate_date']} "
        f"contest_id={summary['contest_id']} players={summary['player_count']} "
        f"path={summary['path']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
