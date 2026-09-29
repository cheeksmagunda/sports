"""Hosted T-40 runner: collect the Real pool, project, freeze, persist (#675).

One cycle:

1. Collect the advertised NHL day from Real Sports (``/home/nhl/next``): the
   daily contest id, the slate games, and every game's player pool.
2. Project each pool player's per-game Real value. Real publishes last
   season's total Real value per player (``rankings.primaryValue``). Real
   player ids are NHL public ids, so dividing by that player's public
   prior-season games played gives a per-game rate on the contest's own
   scale. The rate is shrunk toward the pool's position mean so low-GP
   players do not dominate. Players with no prior GP get the position mean.
   ``injuryStatus == "Out"`` projects 0.
3. Score the pool with ``evaluate_win_freeze_readiness``. That enforces the
   full-pool denominator, every game captured, the zero-boost gate, and the
   T-40 window. Lock proxy is the earliest game start on the Real day (the
   daily contest has no single ``gameId``).
4. Persist one row per (day, contest). Before the window the row is a
   ``preview``. The first cycle inside the window with ``freeze_ready`` writes
   ``frozen``. A frozen row is never overwritten.

``contest_entry`` stays false. This module never enters a contest.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from nhl_oracle.contest.algebra import DEFAULT_SLOT_MULTIPLIERS
from nhl_oracle.contract.schema import NhlCandidate
from nhl_oracle.scheduler.readiness import WinFreezeReadiness, evaluate_win_freeze_readiness
from nhl_oracle.scheduler.t40 import t40_window

PROJECTION_SOURCE = "real_primary_value_per_prior_gp_v0"
# Pseudo-games of the position mean blended into every player's rate.
SHRINK_GAMES = 10.0
OUT_STATUSES = frozenset({"out"})


@dataclass(frozen=True)
class PoolPlayer:
    """One Real pool card for the slate."""

    player_id: int
    name: str
    team: str
    position: str
    game_id: int
    injury_status: str
    primary_value: float | None

    @property
    def out(self) -> bool:
        return self.injury_status.strip().lower() in OUT_STATUSES


@dataclass(frozen=True)
class SlateGame:
    game_id: int
    start_at: datetime
    status: str


@dataclass(frozen=True)
class SlateSnapshot:
    """Everything one cycle collected from Real, before projection."""

    day: date
    contest_id: int
    games: tuple[SlateGame, ...]
    players: tuple[PoolPlayer, ...]
    captured_at: datetime
    games_with_players: frozenset[int] = field(default_factory=frozenset)

    @property
    def lock_at(self) -> datetime | None:
        return min((game.start_at for game in self.games), default=None)


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def parse_home_next(payload: Mapping[str, Any]) -> tuple[date, int, tuple[SlateGame, ...]] | None:
    """Return (day, daily contest id, games) or None when no NHL draft is advertised."""

    latest = payload.get("latestDay")
    content = payload.get("latestDayContent") or {}
    config = content.get("config") or {}
    draft_info = config.get("dailyDraftInfo")
    if not isinstance(latest, str) or not isinstance(draft_info, dict):
        return None
    contest_ids = [
        int(item["id"])
        for item in draft_info.get("contests") or []
        if isinstance(item, dict) and isinstance(item.get("id"), int)
    ]
    if not contest_ids:
        return None
    games: list[SlateGame] = []
    for game in content.get("games") or []:
        if not isinstance(game, dict) or not isinstance(game.get("id"), int):
            continue
        start = _parse_utc(game.get("dateTime"))
        if start is None:
            continue
        games.append(
            SlateGame(game_id=int(game["id"]), start_at=start, status=str(game.get("status") or ""))
        )
    games.sort(key=lambda g: (g.start_at, g.game_id))
    return date.fromisoformat(latest), contest_ids[0], tuple(games)


def parse_game_players(payload: Mapping[str, Any], *, game_id: int) -> tuple[PoolPlayer, ...]:
    """Pool cards from ``/games/{id}/sport/nhl/players``."""

    found: list[PoolPlayer] = []
    for row in payload.get("players") or []:
        if not isinstance(row, dict) or not isinstance(row.get("id"), int):
            continue
        rankings = row.get("rankings") or {}
        primary = rankings.get("primaryValue") if isinstance(rankings, dict) else None
        team = row.get("team") or {}
        name = f"{row.get('firstName') or ''} {row.get('lastName') or ''}".strip()
        found.append(
            PoolPlayer(
                player_id=int(row["id"]),
                name=name or str(row["id"]),
                team=str(team.get("key") or "") if isinstance(team, dict) else "",
                position=str(row.get("position") or "?"),
                game_id=game_id,
                injury_status=str(row.get("injuryStatus") or ""),
                primary_value=float(primary) if isinstance(primary, (int, float)) else None,
            )
        )
    return tuple(found)


def position_bucket(position: str) -> str:
    """Real lists C/LW/RW/D/G. Wingers and centers share one forward bucket."""

    upper = position.upper()
    if upper in {"C", "LW", "RW", "F"}:
        return "F"
    return upper


def project_pool(
    players: Sequence[PoolPlayer],
    prior_games_played: Mapping[int, int],
    *,
    shrink_games: float = SHRINK_GAMES,
) -> dict[int, float]:
    """Per-game Real value for every pool player. Every player gets a value."""

    rates: dict[int, tuple[float, int]] = {}
    by_bucket: dict[str, list[float]] = defaultdict(list)
    for player in players:
        gp = int(prior_games_played.get(player.player_id, 0))
        if player.primary_value is None or gp <= 0:
            continue
        rate = player.primary_value / gp
        rates[player.player_id] = (rate, gp)
        by_bucket[position_bucket(player.position)].append(rate)
    everyone = [rate for rate, _ in rates.values()]
    global_mean = sum(everyone) / len(everyone) if everyone else 0.0
    bucket_mean = {
        bucket: sum(values) / len(values) for bucket, values in by_bucket.items() if values
    }
    projected: dict[int, float] = {}
    for player in players:
        if player.out:
            projected[player.player_id] = 0.0
            continue
        prior = bucket_mean.get(position_bucket(player.position), global_mean)
        if player.player_id in rates:
            rate, gp = rates[player.player_id]
            projected[player.player_id] = (rate * gp + prior * shrink_games) / (gp + shrink_games)
        else:
            projected[player.player_id] = prior
    return projected


@dataclass(frozen=True)
class CycleOutcome:
    """One scored cycle, ready to persist."""

    day: date
    contest_id: int
    status: str  # "preview" | "frozen" | "blocked"
    readiness: WinFreezeReadiness
    lineup: tuple[dict[str, Any], ...]
    lock_at: datetime | None
    decided_at: datetime
    pool_size: int
    games: int

    def to_dict(self) -> dict[str, Any]:
        window = None if self.lock_at is None else t40_window(self.lock_at)
        return {
            "day": self.day.isoformat(),
            "contest_id": self.contest_id,
            "status": self.status,
            "lineup": list(self.lineup),
            "lock_at": None if self.lock_at is None else self.lock_at.isoformat(),
            "t40_open": None if window is None else window.open_at.isoformat(),
            "decided_at": self.decided_at.isoformat(),
            "pool_size": self.pool_size,
            "games": self.games,
            "projection_source": PROJECTION_SOURCE,
            "readiness": self.readiness.to_dict(),
            "contest_entry": False,
        }


def score_cycle(
    snapshot: SlateSnapshot,
    *,
    prior_games_played: Mapping[int, int],
    team_games_played: Mapping[str, int] | None,
    now: datetime,
) -> CycleOutcome:
    """Project the pool and run the existing readiness check on it."""

    projected = project_pool(snapshot.players, prior_games_played)
    captured = snapshot.captured_at.isoformat()
    candidates = tuple(
        NhlCandidate(
            player_id=player.player_id,
            position=player.position,
            score_value=projected[player.player_id],
            captured_at=captured,
        )
        for player in snapshot.players
    )
    readiness = evaluate_win_freeze_readiness(
        candidates=candidates,
        expected_pool_size=len(snapshot.players),
        games_scheduled=len(snapshot.games),
        games_captured=len(snapshot.games_with_players & {g.game_id for g in snapshot.games}),
        projected_values=projected,
        now=now,
        lock_at=snapshot.lock_at,
        team_games_played=team_games_played,
    )
    by_id = {player.player_id: player for player in snapshot.players}
    lineup: tuple[dict[str, Any], ...] = ()
    if readiness.pick_player_ids is not None:
        lineup = tuple(
            {
                "slot": index + 1,
                "multiplier": DEFAULT_SLOT_MULTIPLIERS[index],
                "player_id": player_id,
                "name": by_id[player_id].name,
                "team": by_id[player_id].team,
                "position": by_id[player_id].position,
                "projected_value": round(projected[player_id], 4),
            }
            for index, player_id in enumerate(readiness.pick_player_ids)
        )
    if readiness.freeze_ready:
        status = "frozen"
    elif lineup:
        status = "preview"
    else:
        status = "blocked"
    return CycleOutcome(
        day=snapshot.day,
        contest_id=snapshot.contest_id,
        status=status,
        readiness=readiness,
        lineup=lineup,
        lock_at=snapshot.lock_at,
        decided_at=now,
        pool_size=len(snapshot.players),
        games=len(snapshot.games),
    )


def prior_games_played_from_summaries(*payloads: Mapping[str, Any]) -> dict[int, int]:
    """Map NHL player id to GP from public skater/goalie summary payloads."""

    found: dict[int, int] = {}
    for payload in payloads:
        for row in payload.get("data") or []:
            if not isinstance(row, dict):
                continue
            player_id = row.get("playerId")
            games = row.get("gamesPlayed")
            if isinstance(player_id, int) and isinstance(games, int) and games >= 0:
                found[player_id] = found.get(player_id, 0) + games
    return found
