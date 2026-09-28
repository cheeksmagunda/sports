"""Contest-display sample weights for the HV/TDV train path.

The regression label stays the realized base value. When a pre-lock card
boost is known, the top-k sample weight follows

    value * (top_slot + card_boost)

which is the Highest-value board's rank key. Draft count is not a weight.
With no boost map, the weights match the raw-value top-k used before this
map existed, so a Corpus G fit that has no HV export is unchanged.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from oracle_core.contest_max import iter_hv_json_files
from oracle_core.high_tv import sample_weights_for_labeled_rows

_EASTERN = ZoneInfo("America/New_York")


def sample_weights_contest_display(
    rows: Sequence[Any],
    *,
    boosts: Mapping[tuple[int, int], float] | None = None,
    top_k: int = 5,
    high_weight: float = 4.0,
    base_weight: float = 1.0,
) -> list[float]:
    """Per-row weights. ``boosts`` keys are ``(player_id, game_id)``."""

    wrapped: list[SimpleNamespace] = []
    for row in rows:
        card_boost = None
        if boosts is not None:
            card_boost = float(boosts.get((int(row.player_id), int(row.game_id)), 0.0))
        wrapped.append(
            SimpleNamespace(
                player_id=row.player_id,
                game_id=row.game_id,
                value=row.value,
                did_not_play=bool(getattr(row, "did_not_play", False)),
                card_boost=card_boost,
            )
        )
    return sample_weights_for_labeled_rows(
        wrapped, top_k=top_k, high_weight=high_weight, base_weight=base_weight
    )


def _slate_date(kickoff: datetime) -> str:
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=UTC)
    return kickoff.astimezone(_EASTERN).date().isoformat()


def boosts_for_history_rows(
    rows: Sequence[Any],
    boost_by_slate_player: Mapping[tuple[str, int], float],
) -> dict[tuple[int, int], float]:
    """Join slate-date boosts onto history rows via the Eastern kickoff date.

    Two different boosts for the same player and slate are already dropped by
    :func:`boost_index_from_hv_roots`. A player with no board row is omitted,
    and the weight helper treats that game as boost 0 only when the caller
    passes a complete map. This function returns only matched keys; the caller
    passes the map through, and unmatched rows receive boost 0 inside
    :func:`sample_weights_contest_display`.
    """

    matched: dict[tuple[int, int], float] = {}
    for row in rows:
        kickoff = getattr(row, "kickoff_at", None)
        if not isinstance(kickoff, datetime):
            continue
        slate = _slate_date(kickoff)
        key = (slate, int(row.player_id))
        if key not in boost_by_slate_player:
            continue
        matched[(int(row.player_id), int(row.game_id))] = float(boost_by_slate_player[key])
    return matched


def boost_index_from_hv_roots(roots: Sequence[Path]) -> dict[tuple[str, int], float]:
    """Read HV JSON boards. Disagreeing boosts for one player-slate are dropped."""

    seen: dict[tuple[str, int], list[float]] = defaultdict(list)
    for root in roots:
        for path in iter_hv_json_files(root):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            slate = str(payload.get("slate_date") or payload.get("day") or "")
            players = payload.get("players")
            if not slate or not isinstance(players, list):
                continue
            for player in players:
                if not isinstance(player, dict) or player.get("player_id") is None:
                    continue
                boost = player.get("card_boost")
                if boost is None:
                    boost = 0.0
                seen[(slate, int(player["player_id"]))].append(float(boost))
    resolved: dict[tuple[str, int], float] = {}
    for key, values in seen.items():
        unique = {round(value, 6) for value in values}
        if len(unique) == 1:
            resolved[key] = values[0]
    return resolved


def contest_boost_roots(project: Path) -> list[Path]:
    """Export roots. Missing directories are skipped by the index walker."""

    roots: list[Path] = []
    env_root = os.environ.get("NFL_HV_EXPORT_ROOT", "").strip()
    if env_root:
        roots.append(Path(env_root))
    roots.append(project / "data" / "export" / "hv_boards")
    extra = os.environ.get("NFL_CONTEST_BOOST_ROOT", "").strip()
    if extra:
        roots.append(Path(extra))
    return roots


def load_contest_boosts(project: Path, rows: Sequence[Any]) -> dict[tuple[int, int], float] | None:
    """Boost map for ``fit_model``, or None when no HV board is on disk."""

    index = boost_index_from_hv_roots(contest_boost_roots(project))
    if not index:
        return None
    return boosts_for_history_rows(rows, index)


def contest_display_top_ids(
    projections: Sequence[Any],
    candidates: Sequence[Any],
    *,
    n: int = 5,
) -> tuple[int, ...]:
    """Pre-lock analogue of HV display rank. Does not read draft counts.

    Uses projected base (``conditional_mean``, else ``mean``) times
    ``(top_slot + card_boost)``. The optimizer still commits its own lineup.
    """

    boosts = {int(candidate.player_id): float(candidate.card_boost) for candidate in candidates}
    ranked = sorted(
        projections,
        key=lambda projection: (
            -float(getattr(projection, "conditional_mean", projection.mean))
            * (2.0 + float(boosts.get(int(projection.player_id), 0.0))),
            int(projection.player_id),
        ),
    )
    return tuple(int(projection.player_id) for projection in ranked[:n])
