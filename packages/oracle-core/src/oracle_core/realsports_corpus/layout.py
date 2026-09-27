"""Path helpers for the Real Sports history corpus (issue #526)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

SportCode = Literal["wnba", "nfl", "nba", "nhl"]

ArtifactName = Literal[
    "hv_board",
    "draft_stats",
    "pool_card",
    "game_stats",
    "matchups",
    "feed",
]

ARTIFACT_NAMES: tuple[ArtifactName, ...] = (
    "hv_board",
    "draft_stats",
    "pool_card",
    "game_stats",
    "matchups",
    "feed",
)

_ARTIFACT_FILENAMES: dict[ArtifactName, str] = {
    "hv_board": "hv_board.json",
    "draft_stats": "draft_stats.json",
    "pool_card": "pool_card.json",
    "game_stats": "game_stats.json",
    "matchups": "matchups.json",
    "feed": "feed.json",
}


def season_from_iso_date(iso_date: str) -> str:
    """Return YYYY season key from an ISO date (YYYY-MM-DD...)."""

    if len(iso_date) < 4 or not iso_date[:4].isdigit():
        raise ValueError(f"invalid iso date for season: {iso_date!r}")
    return iso_date[:4]


def slate_or_game_key(
    *,
    slate_date: str | None = None,
    contest_id: int | None = None,
    game_id: int | None = None,
) -> str:
    """Stable directory key for one slate or game.

    Prefer ``game_{id}`` when a game id is known (Corpus G grain), else
    ``slate_{date}_{contest}`` / ``slate_{date}``.
    """

    if game_id is not None:
        return f"game_{int(game_id)}"
    if slate_date is None:
        raise ValueError("slate_date or game_id required")
    if contest_id is not None:
        return f"slate_{slate_date}_{int(contest_id)}"
    return f"slate_{slate_date}"


def artifact_path(
    *,
    sport: SportCode,
    season: str,
    slate_or_game_id: str,
    artifact: ArtifactName,
) -> Path:
    """Relative path ``{sport}/{season}/{slate_or_game_id}/{artifact}.json``."""

    if artifact not in _ARTIFACT_FILENAMES:
        raise ValueError(f"unknown artifact: {artifact!r}")
    return Path(sport) / season / slate_or_game_id / _ARTIFACT_FILENAMES[artifact]
