"""Summarize HV / TDV player boards for Ollama prompts (#574).

Live boards only: missing sport, slate, players, identity, or value raises
``LiveDataRequiredError``. Never invent placeholder names or scores.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ollama_hv_watcher.live import LiveDataRequiredError, require_live


@dataclass(frozen=True)
class BoardSummary:
    """Compact Highest-value / Total Value board digest for prompts."""

    path: str
    sport: str
    slate_key: str
    label: str
    player_count: int
    top_players: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
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
                f"HV/TDV board label={self.label} sport={self.sport} "
                f"slate={self.slate_key} players={self.player_count}"
            ),
            "Top players (highest value / max_value / top_1 style ranks):",
        ]
        for i, row in enumerate(self.top_players[:top_n], start=1):
            name = row["name"] if row.get("name") else row["player_id"]
            value = row.get("value")
            real = row.get("real_score")
            team = row.get("team") or ""
            lines.append(f"  {i}. {name} team={team} value={value} real_score={real}")
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


def _normalize_player(row: dict[str, Any], *, index: int, path: str) -> dict[str, Any]:
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
    real_raw = row.get("real_score")
    if real_raw is None:
        real_raw = row.get("score")
    real_score = (
        _as_float(real_raw, field="real_score|score", context=ctx)
        if real_raw is not None
        else None
    )
    team = row.get("team") if row.get("team") is not None else row.get("team_abbr")
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
) -> BoardSummary:
    if not isinstance(payload, dict):
        raise LiveDataRequiredError("board", context=f"path={path}; not_object")
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
        _normalize_player(p, index=i, path=path) for i, p in enumerate(players_raw)
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
    )


def load_board_summary(path: Path, *, top_n: int = 15) -> BoardSummary:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise LiveDataRequiredError("board", context=f"path={path}; not_object")
    return summarize_board_payload(raw, path=str(path), top_n=top_n)


# Single source for board filenames; training_data_manifest.json globs match.
BOARD_FILENAMES = (
    "hv_board.json",
    "total_value_leaderboard.json",
    "highestBoostedValuePlayers.json",
)


def discover_board_paths(root: Path) -> list[Path]:
    """Find HV/TDV board files (``BOARD_FILENAMES``) under a root."""

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
