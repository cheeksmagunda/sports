"""Export one WNBA Highest-value board into the durable HV corpus layout (#526).

Reads Real Sports contest ``/stats`` ``highestBoostedValuePlayers`` (Total
Value Daily Leaderboard) and appends JSON under a corpus root that is meant
to live in a **separate** GitHub-tracked repo (not the monorepo tree).

Auth: uses existing ``REALSPORTS_STORAGE_STATE_B64GZ`` / storage_state. Never
prints the secret; only logs ``sha256[:8]`` presence. Fail closed if missing
or invalid. Never mints credentials. Never enters contests.

Usage (Codespace login shell)::

    python wnba-oracle/scripts/seed_storage_state.py
    uv run --frozen --package wnba-oracle python wnba-oracle/scripts/export_hv_board.py \\
      --corpus-root /tmp/sports-realsports-corpus --proof-latest-finalized

Or with an explicit contest id::

    ... export_hv_board.py --corpus-root /tmp/sports-realsports-corpus --contest-id 2100
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import sys
from pathlib import Path

import httpx
from oracle_core.hv_board_corpus import HvBoardPlayer, append_hv_board, build_hv_board

from wnba_oracle.ingest.contest_stats import (
    ContestNotFinalized,
    ContestUnavailable,
    fetch_contest_stats,
)
from wnba_oracle.ingest.realsports import (
    PlatformAuthRequired,
    StorageStateMissing,
    headers_or_capture,
)


def _auth_sha8() -> str | None:
    raw = os.environ.get("REALSPORTS_STORAGE_STATE_B64GZ", "").strip()
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]


def _labels_to_players(labels: list) -> list[HvBoardPlayer]:
    players: list[HvBoardPlayer] = []
    for row in labels:
        if row.section != "highestBoostedValuePlayers":
            continue
        players.append(
            HvBoardPlayer(
                player_id=int(row.platform_player_id),
                name=str(row.display_name or ""),
                team=str(row.team_key or ""),
                real_score=row.real_score,
                base=None,
                card_boost=float(row.card_boost) if row.card_boost is not None else None,
                slot=None,
                drafts=row.drafts,
                # Platform ``value`` is stored as real_score on ContestLabel;
                # HV board ranking uses that same field as Total Value label.
                value=row.real_score,
            )
        )
    return players


def _fetch_hv(
    contest_id: int,
    *,
    require_finalized: bool,
) -> tuple[str, list[HvBoardPlayer]]:
    device_uuid = os.environ.get("WNBA_DEVICE_UUID", "wnba-oracle-hv-export")
    device_name = os.environ.get("WNBA_DEVICE_NAME", "wnba-oracle-hv-export")

    async def _headers():
        return await headers_or_capture(device_uuid, device_name)

    headers = asyncio.run(_headers())

    def refresh():
        return asyncio.run(_headers())

    with httpx.Client(timeout=30.0) as client:
        labels = fetch_contest_stats(
            contest_id,
            headers,
            client,
            refresh_headers=refresh,
            require_finalized=require_finalized,
        )
    if not labels:
        raise ContestUnavailable(f"contest {contest_id} returned empty draftStats")
    slate_date = labels[0].slate_date
    players = _labels_to_players(labels)
    if not players:
        raise ContestUnavailable(
            f"contest {contest_id} has no highestBoostedValuePlayers rows"
        )
    return slate_date, players


def _walk_latest_finalized(start_id: int, *, max_steps: int = 40) -> tuple[int, str, list]:
    """Walk contest ids downward until a finalized WNBA HV board is found."""

    last_err: Exception | None = None
    for cid in range(start_id, max(0, start_id - max_steps), -1):
        try:
            slate_date, players = _fetch_hv(cid, require_finalized=True)
            return cid, slate_date, players
        except (ContestNotFinalized, ContestUnavailable) as exc:
            last_err = exc
            continue
        except PlatformAuthRequired:
            raise
    raise ContestUnavailable(
        f"no finalized WNBA HV board in [{start_id - max_steps + 1}, {start_id}]"
        + (f"; last={last_err}" if last_err else "")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-root",
        type=Path,
        required=True,
        help="Root of the separate corpus checkout (receives hv_boards/)",
    )
    parser.add_argument("--contest-id", type=int, default=None)
    parser.add_argument(
        "--proof-latest-finalized",
        action="store_true",
        help="Discover freshest contest then walk back to latest finalized HV board",
    )
    parser.add_argument(
        "--allow-unfinalized",
        action="store_true",
        help="Accept a non-finalized contest (not for durable corpus)",
    )
    args = parser.parse_args(argv)

    sha8 = _auth_sha8()
    if sha8 is None:
        print(
            "export_hv_board: FAIL_CLOSED auth missing "
            "(REALSPORTS_STORAGE_STATE_B64GZ unset). No scrape. Refs #526.",
            file=sys.stderr,
        )
        return 78
    print(f"export_hv_board: auth present sha256[:8]={sha8}")

    try:
        if args.proof_latest_finalized:
            from wnba_oracle.ingest.realsports import discover_wnba_contest_id

            top = asyncio.run(discover_wnba_contest_id())
            if top is None:
                print("export_hv_board: discover_wnba_contest_id returned None", file=sys.stderr)
                return 1
            print(f"export_hv_board: discovered contest_id={top}")
            contest_id, slate_date, players = _walk_latest_finalized(top)
        elif args.contest_id is not None:
            contest_id = args.contest_id
            slate_date, players = _fetch_hv(
                contest_id,
                require_finalized=not args.allow_unfinalized,
            )
        else:
            print(
                "export_hv_board: pass --contest-id or --proof-latest-finalized",
                file=sys.stderr,
            )
            return 2
    except StorageStateMissing as exc:
        print(f"export_hv_board: FAIL_CLOSED storage_state missing: {exc}", file=sys.stderr)
        return 78
    except PlatformAuthRequired as exc:
        print(f"export_hv_board: FAIL_CLOSED platform auth: {exc}", file=sys.stderr)
        return 78
    except (ContestUnavailable, ContestNotFinalized) as exc:
        print(f"export_hv_board: unavailable: {exc}", file=sys.stderr)
        return 1

    doc = build_hv_board(
        sport="wnba",
        slate_date=slate_date,
        contest_id=contest_id,
        players=players,
    )
    summary = append_hv_board(doc, args.corpus_root)
    print(
        "export_hv_board: ok "
        f"sport={summary['sport']} slate={summary['slate_date']} "
        f"contest_id={summary['contest_id']} players={summary['player_count']} "
        f"path={summary['path']} sha12={summary['content_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
