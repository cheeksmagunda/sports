"""Rank the complete eligible pool for the remaining games of a slate.

Research path, not the gated freeze. It walks each upcoming game's roster
(the full eligible universe, no sampling and no minimum-history filter),
joins Real-id Corpus G history, and projects every player. Players without
enough history fall back to their position mean via `project_candidates`
rather than being dropped.

Boosts are not fetched. Under the week-1 zero-boost regime the slot order is
pure descending projected value, so the per-name rating search -- the only
reason to make hundreds of provider calls -- is not needed for a draft.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from nfl_oracle.ingest.realsports import headers_or_capture
from nfl_oracle.recommendations.provider import NFLReader, ObservationStore, parse_game
from nfl_oracle.valuelaw.candidates import build_history_index
from nfl_oracle.valuelaw.project import project_candidates


@dataclass(frozen=True)
class _Candidate:
    """Minimal candidate view carrying only what the projector reads."""

    player_id: int
    name: str
    position: str
    team: str
    opponent: str
    injury_status: str | None
    card_boost: float


@dataclass(frozen=True)
class _Row:
    candidate: _Candidate
    history: Any

    @property
    def player_id(self) -> int:
        return self.candidate.player_id


async def _gather(day: dt.date, spacing: float) -> tuple[list[_Row], list[str], dict[int, str]]:
    headers = await headers_or_capture()
    notes: list[str] = []
    async with httpx.AsyncClient(timeout=25) as client:
        reader = NFLReader(client, headers, ObservationStore(Path("data/raw/observations")))
        content = await reader.day_content(day)
        games = tuple(parse_game(raw) for raw in content.get("games", []))
        now = dt.datetime.now(dt.UTC)
        upcoming = tuple(g for g in games if g.kickoff_at > now)
        notes.append(f"{len(upcoming)} of {len(games)} games still upcoming")

        # Slot order here is plain descending projected value, which is only the
        # optimal commitment while every card boost is zero. Boosts are absent
        # for the whole of NFL week 1 and switch on at week 2, after which
        # selection has to weigh value against the boost the provider assigned
        # and this ranking is no longer the right answer. Rosters do not carry
        # the boost, so sample the rating search and refuse rather than quietly
        # emit a week-1 answer into a boosted week.
        contests = content.get("config", {}).get("dailyDraftInfo", {}).get("contests", [])
        contest_ids = [c.get("id") for c in contests if isinstance(c, dict)]
        if len(contest_ids) == 1 and isinstance(contest_ids[0], int):
            probe = await reader.get(
                "/players/sport/nfl/search",
                query="",
                searchType="ratingLineup",
                day=day.isoformat(),
                contestId=contest_ids[0],
                includeNoOneOption="false",
            )
            sampled = [p.get("multiplierBonus") for p in probe.get("players") or []]
            boosted = [b for b in sampled if isinstance(b, int | float) and b > 0]
            if boosted:
                raise SystemExit(
                    f"refusing to draft: {len(boosted)} of {len(sampled)} sampled players carry a "
                    "non-zero card boost. Descending projected value is only optimal under the "
                    "zero-boost regime. Use the gated freeze path, which models boosts."
                )
            notes.append(f"boost probe: {len(sampled)} sampled, all zero")
        else:
            notes.append("boost probe skipped: contest not uniquely resolvable")

        index = build_history_index()
        rows: list[_Row] = []
        seen: set[int] = set()
        opponents: dict[int, str] = {}
        for game in upcoming:
            payload = await reader.get(f"/games/{game.game_id}/sport/nfl/players")
            players = payload.get("players") or []
            notes.append(f"game {game.game_id}: {len(players)} rostered")
            for player in players:
                pid = player.get("id")
                if not isinstance(pid, int) or pid in seen:
                    continue
                seen.add(pid)
                team_id = player.get("teamId")
                is_home = team_id == game.home_team_id
                team = (player.get("team") or {}).get("key") or (
                    game.home_team if is_home else game.away_team
                )
                opponent = game.away_team if is_home else game.home_team
                opponents[pid] = opponent
                first = player.get("firstName", "")
                last = player.get("lastName", "")
                rows.append(
                    _Row(
                        candidate=_Candidate(
                            player_id=pid,
                            name=f"{first} {last}".strip(),
                            position=player.get("position") or "?",
                            team=team,
                            opponent=opponent,
                            injury_status=player.get("injuryStatus"),
                            card_boost=float(player.get("multiplierBonus") or 0.0),
                        ),
                        history=index.get(pid),
                    )
                )
            await asyncio.sleep(spacing)
    return rows, notes, opponents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=dt.date.today().isoformat())
    parser.add_argument("--spacing", type=float, default=1.0)
    parser.add_argument("--out", default="data/artifacts/full_pool_draft.csv")
    args = parser.parse_args()

    day = dt.date.fromisoformat(args.day)
    rows, notes, opponents = asyncio.run(_gather(day, args.spacing))
    for note in notes:
        print(note)
    if not rows:
        print("no upcoming games -- nothing to draft")
        return 1

    projections = sorted(project_candidates(rows), key=lambda p: p.projected_value, reverse=True)
    modelled = sum(1 for p in projections if p.method == "player_ewma")
    fallback = sum(1 for p in projections if p.method == "position_mean")
    injured = sum(1 for p in projections if p.method == "injury_zero")
    print(
        f"\npool {len(projections)} players: {modelled} from own history, "
        f"{fallback} position-mean fallback, {injured} zeroed as out/inactive"
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["rank", "player", "pos", "team", "opp", "proj", "games", "method", "injury"]
        )
        for rank, p in enumerate(projections, 1):
            writer.writerow(
                [
                    rank,
                    p.name,
                    p.position,
                    p.team,
                    opponents.get(p.player_id, ""),
                    f"{p.projected_value:.3f}",
                    p.prior_games,
                    p.method,
                    p.injury_status or "",
                ]
            )
    print(f"full ranked pool -> {out}")

    print("\nTop 20 of the full pool:")
    for rank, p in enumerate(projections[:20], 1):
        flag = "" if p.method == "player_ewma" else f"  [{p.method}]"
        print(
            f"{rank:2d}. {p.name:26s} {p.position:3s} {p.team:4s} "
            f"proj={p.projected_value:6.3f} games={p.prior_games:3d} {p.injury_status or ''}{flag}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
