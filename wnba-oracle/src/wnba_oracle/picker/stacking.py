"""Pure helpers for contextual lineup-balance decisions.

The optimizer receives already-enriched projections. This module only resolves
game identity, describes lineup composition, and defines the preferred shape
for a slate. It performs no I/O and makes no independent performance forecast.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

POLICY_VERSION = "contextual-stacking-v1"


class _StackPlayer(Protocol):
    @property
    def player_id(self) -> int: ...

    @property
    def team(self) -> str: ...

    @property
    def opponent(self) -> str: ...

    @property
    def game_id(self) -> str: ...


@dataclass(frozen=True)
class StackPreference:
    """Preferred, soft lineup shape for a metadata-complete slate."""

    min_games: int
    max_players_per_game: int
    target_team_count: int


@dataclass(frozen=True)
class LineupShape:
    """Auditable team and game composition for one five-player candidate."""

    game_count: int | None
    team_count: int
    max_players_per_game: int | None
    max_players_per_team: int
    game_counts: tuple[tuple[str, int], ...]
    team_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class StackingDecision:
    """Versioned explanation attached to every optimizer recommendation."""

    policy_version: str
    enabled: bool
    reason: str
    metadata_quality: str
    slate_game_count: int | None
    slate_team_count: int
    preferred_min_games: int | None
    preferred_max_players_per_game: int | None
    preferred_team_count: int
    effective_max_players_per_team: int
    team_cap_reason: str
    selected_game_count: int | None
    selected_team_count: int
    selected_max_players_per_game: int | None
    selected_max_players_per_team: int
    selected_game_counts: tuple[tuple[str, int], ...]
    selected_team_counts: tuple[tuple[str, int], ...]
    selected_objective: float
    best_unrestricted_objective: float
    best_game_balanced_objective: float | None
    best_fully_balanced_objective: float | None
    objective_sacrifice: float
    override_margin: float
    legacy_stack_bonus_ignored: bool


def canonical_matchup_key(team: str, opponent: str) -> str:
    """Return a stable fallback key for a reciprocal team/opponent pair."""
    left = team.strip().upper()
    right = opponent.strip().upper()
    if not left or not right or left == right:
        return ""
    first, second = sorted((left, right))
    return f"teams:{first}|{second}"


def _provider_metadata_is_complete(specs: Sequence[_StackPlayer]) -> bool:
    groups: dict[str, set[str]] = {}
    games_by_team: dict[str, set[str]] = {}
    opponents_by_team: dict[str, set[str]] = {}
    for spec in specs:
        game_id = str(getattr(spec, "game_id", "") or "").strip()
        team = str(spec.team or "").strip().upper()
        opponent = str(spec.opponent or "").strip().upper()
        if not game_id or not team:
            return False
        groups.setdefault(game_id, set()).add(team)
        games_by_team.setdefault(team, set()).add(game_id)
        if opponent:
            opponents_by_team.setdefault(team, set()).add(opponent)
    if (
        not groups
        or any(len(teams) != 2 for teams in groups.values())
        or any(len(game_ids) != 1 for game_ids in games_by_team.values())
        or any(len(opponents) != 1 for opponents in opponents_by_team.values())
    ):
        return False
    for game_id, teams in groups.items():
        for team in teams:
            opponents = opponents_by_team.get(team, set())
            if opponents and opponents != teams - {team}:
                return False
            opponent = next(iter(teams - {team}))
            if opponent in games_by_team and games_by_team[opponent] != {game_id}:
                return False
    return True


def _fallback_metadata_is_complete(specs: Sequence[_StackPlayer]) -> bool:
    pairs: set[tuple[str, str]] = set()
    opponents_by_team: dict[str, set[str]] = {}
    games_by_team: dict[str, set[str]] = {}
    for spec in specs:
        team = str(spec.team or "").strip().upper()
        opponent = str(spec.opponent or "").strip().upper()
        game_key = canonical_matchup_key(team, opponent)
        if not game_key:
            return False
        pairs.add((team, opponent))
        opponents_by_team.setdefault(team, set()).add(opponent)
        games_by_team.setdefault(team, set()).add(game_key)
    return (
        bool(pairs)
        and all(len(opponents) == 1 for opponents in opponents_by_team.values())
        and all(len(game_keys) == 1 for game_keys in games_by_team.values())
        and all((opponent, team) in pairs for team, opponent in pairs)
    )


def resolve_game_keys(
    specs: Sequence[_StackPlayer],
) -> tuple[dict[int, str], str, int | None]:
    """Resolve provider IDs first, then a validated reciprocal fallback.

    A mixed provider/fallback slate never mixes identity namespaces. If every
    provider ID is not present and internally consistent, the entire slate uses
    reciprocal team/opponent metadata or is marked incomplete.
    """
    if _provider_metadata_is_complete(specs):
        keys = {int(spec.player_id): f"realsports:{str(spec.game_id).strip()}" for spec in specs}
        return keys, "provider_game_id", len(set(keys.values()))
    if _fallback_metadata_is_complete(specs):
        keys = {
            int(spec.player_id): canonical_matchup_key(spec.team, spec.opponent) for spec in specs
        }
        return keys, "team_opponent_fallback", len(set(keys.values()))
    return {int(spec.player_id): "" for spec in specs}, "incomplete", None


def preference_for_slate(n_games: int, n_teams: int) -> StackPreference:
    """Return the soft balance target for one-, two-, and larger-game slates."""
    if n_games <= 1:
        return StackPreference(
            min_games=1,
            max_players_per_game=5,
            target_team_count=min(2, n_teams),
        )
    if n_games == 2:
        return StackPreference(
            min_games=2,
            max_players_per_game=3,
            target_team_count=min(4, n_teams),
        )
    return StackPreference(
        min_games=2,
        max_players_per_game=2,
        target_team_count=min(4, n_teams),
    )


def describe_lineup(
    combo: tuple[int, ...],
    teams: Sequence[str],
    game_keys: Sequence[str],
) -> LineupShape:
    """Describe a candidate without inventing missing team or game identity."""
    team_counter = Counter(str(teams[index] or "").strip().upper() for index in combo)
    team_counter.pop("", None)
    selected_game_keys = [str(game_keys[index] or "") for index in combo]
    games_complete = all(selected_game_keys)
    game_counter = Counter(selected_game_keys) if games_complete else Counter()
    return LineupShape(
        game_count=len(game_counter) if games_complete else None,
        team_count=len(team_counter),
        max_players_per_game=max(game_counter.values()) if game_counter else None,
        max_players_per_team=max(team_counter.values()) if team_counter else 0,
        game_counts=tuple(sorted(game_counter.items())),
        team_counts=tuple(sorted(team_counter.items())),
    )


def meets_game_preference(shape: LineupShape, preference: StackPreference) -> bool:
    """Whether a lineup meets the game-level part of the soft target."""
    return (
        shape.game_count is not None
        and shape.max_players_per_game is not None
        and shape.game_count >= preference.min_games
        and shape.max_players_per_game <= preference.max_players_per_game
    )


def meets_full_preference(shape: LineupShape, preference: StackPreference) -> bool:
    """Whether a lineup also reaches the desired distinct-team coverage."""
    return (
        meets_game_preference(shape, preference)
        and shape.team_count >= preference.target_team_count
    )


def hard_lineup_shape_for_games(n_games: int) -> StackPreference:
    """Return the deterministic anti-stacking shape for a slate's game count."""
    if n_games <= 1:
        return StackPreference(min_games=1, max_players_per_game=5, target_team_count=2)
    if n_games == 2:
        return StackPreference(min_games=2, max_players_per_game=3, target_team_count=4)
    if n_games == 3:
        return StackPreference(min_games=3, max_players_per_game=2, target_team_count=5)
    if n_games == 4:
        return StackPreference(min_games=4, max_players_per_game=2, target_team_count=5)
    return StackPreference(min_games=5, max_players_per_game=1, target_team_count=5)
