"""Contest-display sample weights for the HV/TDV train path.

The regression label stays the realized base value. When a pre-lock card
boost is known, each contest board (one Eastern slate) high-weights its
top 10 by

    value * (top_slot + card_boost)

which is the Highest-value board's rank key. Draft count is not a weight.
With no boost map, the weights stay the per-game raw-value top 5 used
before this map existed, so a Corpus G fit that has no HV export is unchanged.
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

from oracle_core.contest_max import (
    LABEL_WINDOW,
    contest_display_rank_weights,
    display_contest_value,
    iter_hv_json_files,
)
from oracle_core.high_tv import sample_weights_for_labeled_rows

_EASTERN = ZoneInfo("America/New_York")
# Raw-value fallback stays the pre-window top five. Display rank uses the
# contest-board window (default 10) only when a boost map is supplied.
RAW_TOP_K = 5
DISPLAY_TOP_K = LABEL_WINDOW


def display_top_k_from_env(env: Mapping[str, str] | None = None) -> int:
    """Read ``NFL_TRAIN_DISPLAY_TOP_K``. Unset means 10. Garbage fails closed.

    The value is the display-rank window used when a card-boost map is
    present. It does not change the raw-value fallback.
    """

    source = os.environ if env is None else env
    raw = source.get("NFL_TRAIN_DISPLAY_TOP_K", "").strip()
    if not raw:
        return DISPLAY_TOP_K
    if not raw.isdigit():
        raise ValueError("nfl_train_display_top_k_invalid")
    value = int(raw)
    if value < 1:
        raise ValueError("nfl_train_display_top_k_invalid")
    return value


def resolve_train_top_k(
    *,
    boosts_present: bool,
    top_k: int | None = None,
    display_top_k: int = DISPLAY_TOP_K,
) -> int:
    """Explicit ``top_k`` wins. Otherwise 10 on a boost map and 5 without one."""

    if top_k is not None:
        if top_k < 1:
            raise ValueError("train_top_k_invalid")
        return top_k
    if display_top_k < 1:
        raise ValueError("train_top_k_invalid")
    return display_top_k if boosts_present else RAW_TOP_K


def _board_key(row: Any) -> str:
    """One contest board. Eastern kickoff date, else contest id, else game."""

    kickoff = getattr(row, "kickoff_at", None)
    if isinstance(kickoff, datetime):
        return f"slate:{_slate_date(kickoff)}"
    contest_id = getattr(row, "contest_id", None)
    if isinstance(contest_id, int) and contest_id > 0:
        return f"contest:{contest_id}"
    return f"game:{int(row.game_id)}"


def sample_weights_contest_display(
    rows: Sequence[Any],
    *,
    boosts: Mapping[tuple[int, int], float] | None = None,
    top_k: int | None = None,
    display_top_k: int = DISPLAY_TOP_K,
    high_weight: float = 4.0,
    base_weight: float = 1.0,
) -> list[float]:
    """Per-row weights. ``boosts`` keys are ``(player_id, game_id)``.

    A boost map ranks each contest board by ``value * (2 + card_boost)`` and
    high-weights that board's top window (default 10). Players on the same
    Eastern slate share one board, so a Sunday slate does not take a top
    window from every game. No boost map keeps per-game raw-value top-k
    (default 5). Draft count is not read.
    """

    resolved = resolve_train_top_k(
        boosts_present=boosts is not None, top_k=top_k, display_top_k=display_top_k
    )
    if boosts is None:
        wrapped = [
            SimpleNamespace(
                player_id=row.player_id,
                game_id=row.game_id,
                value=row.value,
                did_not_play=bool(getattr(row, "did_not_play", False)),
            )
            for row in rows
        ]
        return sample_weights_for_labeled_rows(
            wrapped, top_k=resolved, high_weight=high_weight, base_weight=base_weight
        )

    # Best display value per player on the board. One player takes one slot.
    boards: dict[str, dict[int, tuple[float, float]]] = defaultdict(dict)
    for row in rows:
        if bool(getattr(row, "did_not_play", False)):
            continue
        value = getattr(row, "value", None)
        if value is None:
            continue
        player_id = int(row.player_id)
        game_id = int(row.game_id)
        board_key = _board_key(row)
        boost = float(boosts.get((player_id, game_id), 0.0))
        display = display_contest_value(float(value), boost)
        current = boards[board_key].get(player_id)
        if current is None or display > display_contest_value(current[0], current[1]):
            boards[board_key][player_id] = (float(value), boost)

    weight_by_board_player: dict[tuple[str, int], float] = {}
    for key, mapping in boards.items():
        values = {pid: pair[0] for pid, pair in mapping.items()}
        boost_map = {pid: pair[1] for pid, pair in mapping.items()}
        ranked = contest_display_rank_weights(
            values,
            boost_map,
            top_k=resolved,
            high_weight=high_weight,
            base_weight=base_weight,
        )
        for pid, weight in ranked.items():
            weight_by_board_player[(key, pid)] = weight

    out: list[float] = []
    for row in rows:
        if bool(getattr(row, "did_not_play", False)) or getattr(row, "value", None) is None:
            out.append(base_weight)
            continue
        out.append(weight_by_board_player.get((_board_key(row), int(row.player_id)), base_weight))
    return out


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
