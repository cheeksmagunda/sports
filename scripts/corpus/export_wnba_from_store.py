"""Export WNBA HV boards from durable stores (zero Real Sports calls).

Preferred sources (in order):

1. ``--labels-csv`` pointing at ``slate_labels.csv`` from the orphan
   ``backups`` branch (GitHub-tracked durable corpus).
2. ``DATABASE_URL`` / ``DATABASE_PUBLIC_URL`` Postgres ``slate_labels`` rows
   with ``section = highestBoostedValuePlayers``.

Writes under ``--corpus-root`` using layout
``{sport}/{season}/{slate_or_game_id}/hv_board.json`` (#526).

Usage::

    uv run --frozen --package wnba-oracle python scripts/corpus/export_wnba_from_store.py \\
      --corpus-root /tmp/sports-realsports-corpus \\
      --labels-csv /path/to/slate_labels.csv --limit-slates 3
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from pathlib import Path

from oracle_core.hv_board_corpus import (
    HvBoardDocument,
    HvBoardPlayer,
    append_hv_board,
    build_hv_board,
)


def _players_from_rows(rows: list[dict[str, str]]) -> list[HvBoardPlayer]:
    players: list[HvBoardPlayer] = []
    for row in rows:
        if row.get("section") != "highestBoostedValuePlayers":
            continue
        real_raw = (row.get("real_score") or "").strip()
        boost_raw = (row.get("card_boost") or "").strip()
        drafts_raw = (row.get("drafts") or "").strip()
        real_score = float(real_raw) if real_raw else None
        players.append(
            HvBoardPlayer(
                player_id=int(row["platform_player_id"]),
                name=str(row.get("display_name") or ""),
                team=str(row.get("team_key") or ""),
                real_score=real_score,
                base=None,
                card_boost=float(boost_raw) if boost_raw else None,
                slot=None,
                drafts=int(float(drafts_raw)) if drafts_raw else None,
                value=real_score,
            )
        )
    return players


def _group_csv(path: Path) -> dict[tuple[str, int], list[dict[str, str]]]:
    groups: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("section") != "highestBoostedValuePlayers":
                continue
            key = (str(row["slate_date"]), int(row["contest_id"]))
            groups[key].append(row)
    return groups


def _group_postgres() -> dict[tuple[str, int], list[dict[str, str]]]:
    from sqlalchemy import create_engine, text

    scripts_dir = Path(__file__).resolve().parents[2] / "wnba-oracle" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from corpus_backup_common import (
        portable_postgres_url,  # type: ignore[import-not-found]
    )

    url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL or DATABASE_PUBLIC_URL required without --labels-csv"
        )
    engine = create_engine(portable_postgres_url(url))
    q = text(
        "SELECT contest_id, slate_date, section, platform_player_id, display_name, "
        "team_key, card_boost, drafts, real_score FROM slate_labels "
        "WHERE section = 'highestBoostedValuePlayers' "
        "ORDER BY slate_date, contest_id, platform_player_id"
    )
    groups: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    with engine.connect() as conn:
        for row in conn.execute(q):
            mapping = dict(row._mapping)
            key = (str(mapping["slate_date"]), int(mapping["contest_id"]))
            groups[key].append(
                {
                    "contest_id": str(mapping["contest_id"]),
                    "slate_date": str(mapping["slate_date"]),
                    "section": str(mapping["section"]),
                    "platform_player_id": str(mapping["platform_player_id"]),
                    "display_name": str(mapping.get("display_name") or ""),
                    "team_key": str(mapping.get("team_key") or ""),
                    "card_boost": ""
                    if mapping.get("card_boost") is None
                    else str(mapping["card_boost"]),
                    "drafts": ""
                    if mapping.get("drafts") is None
                    else str(mapping["drafts"]),
                    "real_score": ""
                    if mapping.get("real_score") is None
                    else str(mapping["real_score"]),
                }
            )
    engine.dispose()
    return groups


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--labels-csv", type=Path, default=None)
    parser.add_argument("--limit-slates", type=int, default=0, help="0 = all")
    args = parser.parse_args(argv)

    if args.labels_csv is not None:
        if not args.labels_csv.is_file():
            print(
                f"export_wnba_from_store: missing csv {args.labels_csv}",
                file=sys.stderr,
            )
            return 1
        groups = _group_csv(args.labels_csv)
        source = f"backups_csv:{args.labels_csv.name}"
    else:
        try:
            groups = _group_postgres()
        except Exception as exc:  # noqa: BLE001 — CLI surface
            print(
                f"export_wnba_from_store: postgres failed ({type(exc).__name__})",
                file=sys.stderr,
            )
            return 1
        source = "postgres:slate_labels"

    if not groups:
        print(
            "export_wnba_from_store: no highestBoostedValuePlayers rows",
            file=sys.stderr,
        )
        return 1

    keys = sorted(groups.keys(), reverse=True)
    if args.limit_slates > 0:
        keys = keys[: args.limit_slates]

    wrote = 0
    for slate_date, contest_id in keys:
        players = _players_from_rows(groups[(slate_date, contest_id)])
        if not players:
            continue
        built = build_hv_board(
            sport="wnba",
            slate_date=slate_date,
            contest_id=contest_id,
            players=players,
        )
        doc = HvBoardDocument(
            sport=built.sport,
            year=built.year,
            slate_date=built.slate_date,
            contest_id=built.contest_id,
            section=built.section,
            scraped_at=built.scraped_at,
            players=built.players,
            schema_version=built.schema_version,
            source=source,
        )
        summary = append_hv_board(doc, args.corpus_root)
        print(
            "export_wnba_from_store: ok "
            f"slate={summary['slate_date']} contest_id={summary['contest_id']} "
            f"players={summary['player_count']} path={summary['path']} "
            f"wrote={summary.get('wrote')}"
        )
        wrote += 1
    print(f"export_wnba_from_store: done slates={wrote} source={source}")
    return 0 if wrote else 1


if __name__ == "__main__":
    raise SystemExit(main())
