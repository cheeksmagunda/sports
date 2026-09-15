"""Rank the complete eligible pool for the remaining games of a slate, and
produce a boost-aware five-card recommendation.

Research and manual-fallback path, not the gated freeze. It collects the full
eligible universe -- no sampling and no minimum-history filter -- through the
same audited `NFLReader.collect()` sweep the production pipeline uses, so
every candidate carries its real, provider-published `card_boost` rather than
a zero-filled placeholder. It then joins Real-id Corpus G history and projects
every player; players without enough history fall back to their position mean
via `project_candidates` rather than being dropped.

Slot selection uses `nfl_oracle.valuelaw.project.recommend_slots`, which is
boost-aware: it holds under both the zero-boost week-1 regime and the live
card-boost table from week 2 on, instead of refusing once boosts go live.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import datetime as dt
from pathlib import Path

import httpx

from nfl_oracle.ingest.realsports import headers_or_capture
from nfl_oracle.recommendations.provider import NFLReader, ObservationStore
from nfl_oracle.recommendations.schema import Slate
from nfl_oracle.valuelaw.candidates import build_history_index, join_history
from nfl_oracle.valuelaw.project import CandidateProjection, project_candidates, recommend_slots


async def _collect(day: dt.date, contest_id: int | None) -> Slate:
    headers = await headers_or_capture()
    async with httpx.AsyncClient(timeout=25) as client:
        reader = NFLReader(client, headers, ObservationStore(Path("data/raw/observations")))
        return await reader.collect(day, contest_id=contest_id)


def _print_ranked_pool(projections: list[CandidateProjection]) -> None:
    print("\nTop 20 of the full pool (raw projected value, not the boost-aware pick):")
    for rank, p in enumerate(projections[:20], 1):
        flag = "" if p.method == "player_ewma" else f"  [{p.method}]"
        print(
            f"{rank:2d}. {p.name:26s} {p.position:3s} {p.team:4s} "
            f"proj={p.projected_value:6.3f} boost={p.card_boost:.1f} "
            f"games={p.prior_games:3d} {p.injury_status or ''}{flag}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=dt.date.today().isoformat())
    parser.add_argument("--contest-id", type=int, default=None)
    parser.add_argument("--out", default="data/artifacts/full_pool_draft.csv")
    args = parser.parse_args()

    day = dt.date.fromisoformat(args.day)
    slate = asyncio.run(_collect(day, args.contest_id))
    print(
        f"slate {slate.contest.contest_id}: {len(slate.candidates)} candidates, "
        f"boost_regime={slate.boost_regime} (max {slate.boost_max}, "
        f"{slate.boost_nonzero_count} nonzero)"
    )

    rows = join_history(slate.candidates, build_history_index())
    opponent_by_id = {c.player_id: c.opponent for c in slate.candidates}
    projections = sorted(project_candidates(rows), key=lambda p: p.projected_value, reverse=True)
    modelled = sum(1 for p in projections if p.method == "player_ewma")
    fallback = sum(1 for p in projections if p.method == "position_mean")
    injured = sum(1 for p in projections if p.method == "injury_zero")
    print(
        f"pool {len(projections)} players: {modelled} from own history, "
        f"{fallback} position-mean fallback, {injured} zeroed as out/inactive"
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["rank", "player", "pos", "team", "opp", "proj", "boost", "games", "method", "injury"]
        )
        for rank, p in enumerate(projections, 1):
            writer.writerow(
                [
                    rank,
                    p.name,
                    p.position,
                    p.team,
                    opponent_by_id.get(p.player_id, ""),
                    f"{p.projected_value:.3f}",
                    f"{p.card_boost:.1f}",
                    p.prior_games,
                    p.method,
                    p.injury_status or "",
                ]
            )
    print(f"full ranked pool -> {out}")

    _print_ranked_pool(projections)

    try:
        recommendations = recommend_slots(projections)
    except ValueError as exc:
        print(f"\ncould not produce a five-card pick: {exc}")
        return 1

    print("\nBoost-aware five-card pick:")
    for rec in recommendations:
        p = rec.projection
        print(
            f"slot {rec.slot} (x{rec.slot_multiplier}): {p.name:26s} {p.position:3s} {p.team:4s} "
            f"proj={p.projected_value:6.3f} boost={p.card_boost:.1f} "
            f"expected={rec.expected_total_value:6.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
