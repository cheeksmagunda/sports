"""Summarize HV / TDV player boards for Ollama prompts (#574).

Live boards only: missing sport, slate, players, identity, or value raises
``LiveDataRequiredError``. Never invent placeholder names or scores.

Leak stop: live advice only ever sees PRE-GAME boards. A board used for a
live tick must carry ``phase == "pregame"`` and is refused when
``game_status == "final"`` or when any player carries an outcome field
(``real_score``, ``score``, or any ``actual*`` key). Post-game boards load
only through the explicit history path (``load_history_board_summary``);
they are never auto-discovered for live ticks.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ollama_hv_watcher.live import LiveDataRequiredError, require_live

BoardMode = Literal["pregame", "history"]

PREGAME_PHASE = "pregame"
LIVE_BOARD_FILENAME = "hv_board.json"
# Player keys that only exist once games are played. Any of them on a board
# means the board is post-game and must never feed live advice.
OUTCOME_PLAYER_KEYS = frozenset({"real_score", "score"})
OUTCOME_PLAYER_PREFIX = "actual"
FINAL_GAME_STATUSES = frozenset({"final", "finalized", "completed", "closed"})


@dataclass(frozen=True)
class BoardSummary:
    """Compact Highest-value / Total Value board digest for prompts."""

    path: str
    sport: str
    slate_key: str
    label: str
    player_count: int
    top_players: tuple[dict[str, Any], ...]
    phase: str = "history"
    section: str = ""

    @property
    def is_pregame(self) -> bool:
        return self.phase == PREGAME_PHASE

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "section": self.section,
            "path": self.path,
            "sport": self.sport,
            "slate_key": self.slate_key,
            "label": self.label,
            "player_count": self.player_count,
            "top_players": list(self.top_players),
        }

    def prompt_block(self, *, top_n: int = 10) -> str:
        lines = [
            (
                f"HV/TDV board phase={self.phase} label={self.label} sport={self.sport} "
                f"slate={self.slate_key} players={self.player_count}"
            ),
            "Top players (highest value / max_value / top_1 style ranks):",
        ]
        for i, row in enumerate(self.top_players[:top_n], start=1):
            name = row["name"] if row.get("name") else row["player_id"]
            value = row.get("value")
            real = row.get("real_score")
            team = row.get("team") or ""
            line = f"  {i}. {name} team={team} value={value}"
            if not self.is_pregame and "real_score" in row:
                line += f" real_score={real}"
            lines.append(line)
        return "\n".join(lines)


def _as_float(value: Any, *, field: str, context: str) -> float:
    if value is None:
        raise LiveDataRequiredError(field, context=context)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise LiveDataRequiredError(
            field,
            context=f"{context}; unparseable={value!r}",
        ) from exc


def _outcome_keys(row: dict[str, Any]) -> list[str]:
    return sorted(
        str(key)
        for key in row
        if str(key) in OUTCOME_PLAYER_KEYS
        or str(key).lower().startswith(OUTCOME_PLAYER_PREFIX)
    )


def assert_pregame_payload(payload: dict[str, Any], *, path: str = "") -> None:
    """Refuse any board that is not provably pre-game (leak stop)."""

    ctx = f"board={path}"
    phase = payload.get("phase")
    if phase != PREGAME_PHASE:
        raise LiveDataRequiredError(
            "phase",
            context=f"{ctx}; live advice requires phase='pregame' got={phase!r}",
        )
    status = str(payload.get("game_status") or "").strip().lower()
    if status in FINAL_GAME_STATUSES:
        raise LiveDataRequiredError(
            "game_status",
            context=f"{ctx}; refuse post-game board game_status={status!r}",
        )
    players = payload.get("players")
    if not isinstance(players, list):
        players = payload.get("highestBoostedValuePlayers")
    if isinstance(players, list):
        for index, row in enumerate(players):
            if isinstance(row, dict) and (leaked := _outcome_keys(row)):
                raise LiveDataRequiredError(
                    f"players[{index}].{leaked[0]}",
                    context=(
                        f"{ctx}; refuse outcome fields {leaked} on a pregame board"
                    ),
                )


def _normalize_player(
    row: dict[str, Any], *, index: int, path: str, pregame: bool = False
) -> dict[str, Any]:
    ctx = f"board={path} player_index={index}"
    if not isinstance(row, dict):
        raise LiveDataRequiredError(f"players[{index}]", context=ctx)
    player_id = (
        row.get("player_id") if row.get("player_id") is not None else row.get("id")
    )
    name = row.get("name") if row.get("name") is not None else row.get("player_name")
    if player_id in (None, "") and (name is None or str(name).strip() == ""):
        raise LiveDataRequiredError(
            "player_id|name",
            context=f"{ctx}; refuse anonymous placeholder player",
        )
    if "value" in row:
        value = _as_float(row.get("value"), field="value", context=ctx)
    elif "max_value" in row:
        value = _as_float(row.get("max_value"), field="max_value", context=ctx)
    else:
        raise LiveDataRequiredError("value|max_value", context=ctx)
    team = row.get("team") if row.get("team") is not None else row.get("team_abbr")
    if pregame:
        out: dict[str, Any] = {
            "player_id": player_id,
            "name": name,
            "team": team,
            "value": value,
            "slot": row.get("slot"),
            "drafts": row.get("drafts"),
        }
        for key in ("position", "opponent", "card_boost", "slot_multiplier"):
            if row.get(key) is not None:
                out[key] = row.get(key)
        return out
    real_raw = row.get("real_score")
    if real_raw is None:
        real_raw = row.get("score")
    real_score = (
        _as_float(real_raw, field="real_score|score", context=ctx)
        if real_raw is not None
        else None
    )
    return {
        "player_id": player_id,
        "name": name,
        "team": team,
        "value": value,
        "real_score": real_score,
        "slot": row.get("slot"),
        "drafts": row.get("drafts"),
    }


def summarize_board_payload(
    payload: dict[str, Any],
    *,
    path: str = "",
    top_n: int = 15,
    mode: BoardMode = "history",
) -> BoardSummary:
    """Summarize a board.

    ``mode="pregame"`` enforces the leak stop (see module docstring) and
    strips outcome fields; ``mode="history"`` is the explicit post-game
    path and must never be used for live ticks.
    """

    if not isinstance(payload, dict):
        raise LiveDataRequiredError("board", context=f"path={path}; not_object")
    if mode not in ("pregame", "history"):
        raise ValueError(f"unknown_board_mode:{mode}")
    pregame = mode == "pregame"
    if pregame:
        assert_pregame_payload(payload, path=path)
    sport = require_live(payload.get("sport"), "sport", context=f"board={path}")
    slate_key = (
        payload.get("slate_key")
        or payload.get("slate_or_game_id")
        or payload.get("slate_date")
    )
    slate_key = require_live(slate_key, "slate_key", context=f"board={path}")

    players_raw = payload.get("players")
    if not isinstance(players_raw, list):
        players_raw = payload.get("highestBoostedValuePlayers")
    if not isinstance(players_raw, list):
        raise LiveDataRequiredError(
            "players|highestBoostedValuePlayers",
            context=f"board={path}",
        )
    if not players_raw:
        raise LiveDataRequiredError("players", context=f"board={path}; empty")

    normalized = [
        _normalize_player(p, index=i, path=path, pregame=pregame)
        for i, p in enumerate(players_raw)
    ]
    normalized.sort(
        key=lambda p: (
            -p["value"],
            str(p.get("player_id") or p.get("name") or ""),
        )
    )
    if "label" in payload and payload["label"] not in (None, ""):
        label = str(payload["label"])
    elif "section" in payload and payload["section"] not in (None, ""):
        label = str(payload["section"])
    else:
        raise LiveDataRequiredError(
            "label|section",
            context=f"board={path}; refuse invented section name",
        )
    return BoardSummary(
        path=path,
        sport=str(sport),
        slate_key=str(slate_key),
        label=label,
        player_count=len(normalized),
        top_players=tuple(normalized[:top_n]),
        phase=PREGAME_PHASE if pregame else "history",
        section=str(payload.get("section") or ""),
    )


def _read_board(path: Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise LiveDataRequiredError("board", context=f"path={path}; not_object")
    return raw


# Single source for board filenames; training_data_manifest.json globs match.
BOARD_FILENAMES = (
    "hv_board.json",
    "total_value_leaderboard.json",
    "highestBoostedValuePlayers.json",
)


def discover_board_paths(root: Path) -> list[Path]:
    """Find HV/TDV board files (``BOARD_FILENAMES``) under a HISTORY root.

    Inventory/history use only; live ticks use ``armed_board_paths``.
    """

    root = Path(root)
    if not root.is_dir():
        return []
    found: list[Path] = []
    for name in BOARD_FILENAMES:
        found.extend(sorted(root.rglob(name)))
    seen: set[Path] = set()
    out: list[Path] = []
    for path in found:
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def load_pregame_board_summary(path: Path, *, top_n: int = 15) -> BoardSummary:
    """Load a board for LIVE advice; refuses anything not provably pre-game."""

    return summarize_board_payload(
        _read_board(path), path=str(path), top_n=top_n, mode="pregame"
    )


def load_history_board_summary(path: Path, *, top_n: int = 15) -> BoardSummary:
    """Explicit post-game history path (operator-named file only)."""

    return summarize_board_payload(
        _read_board(path), path=str(path), top_n=top_n, mode="history"
    )


def armed_board_paths(data_root: Path, slates: Iterable[Any]) -> list[Path]:
    """Live board discovery: ``data_root/<sport>/<slate_id>/hv_board.json``.

    Only the given (armed) slates are considered. Never walks
    ``data_root/boards/**`` or any other tree, so historical post-game
    boards cannot leak into a live tick.
    """

    out: list[Path] = []
    for slate in slates:
        sport = str(slate.sport).replace("/", "_")
        slate_id = str(slate.slate_id).replace("/", "_")
        candidate = Path(data_root) / sport / slate_id / LIVE_BOARD_FILENAME
        if candidate.is_file() and candidate not in out:
            out.append(candidate)
    return out
