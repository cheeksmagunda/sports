"""Summarize HV / TDV player boards for Ollama prompts (#574)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BoardSummary:
    """Compact Highest-value / Total Value board digest for prompts."""

    path: str
    sport: str | None
    slate_key: str | None
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
                f"HV/TDV board label={self.label} sport={self.sport or '?'} "
                f"slate={self.slate_key or '?'} players={self.player_count}"
            ),
            "Top players (highest value / max_value / top_1 style ranks):",
        ]
        for i, row in enumerate(self.top_players[:top_n], start=1):
            name = row.get("name") or row.get("player_id") or "?"
            value = row.get("value")
            real = row.get("real_score")
            team = row.get("team") or ""
            lines.append(f"  {i}. {name} team={team} value={value} real_score={real}")
        return "\n".join(lines)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_player(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "player_id": row.get("player_id") or row.get("id"),
        "name": row.get("name") or row.get("player_name"),
        "team": row.get("team") or row.get("team_abbr"),
        "value": _as_float(
            row.get("value") if "value" in row else row.get("max_value")
        ),
        "real_score": _as_float(row.get("real_score") or row.get("score")),
        "slot": row.get("slot"),
        "drafts": row.get("drafts"),
    }


def summarize_board_payload(
    payload: dict[str, Any],
    *,
    path: str = "",
    top_n: int = 15,
) -> BoardSummary:
    players_raw = payload.get("players")
    if not isinstance(players_raw, list):
        players_raw = payload.get("highestBoostedValuePlayers") or []
    if not isinstance(players_raw, list):
        players_raw = []

    normalized = [_normalize_player(p) for p in players_raw if isinstance(p, dict)]
    normalized.sort(
        key=lambda p: (
            -(p["value"] if p["value"] is not None else float("-inf")),
            str(p.get("player_id") or ""),
        )
    )
    label = str(
        payload.get("label") or payload.get("section") or "total_value_leaderboard"
    )
    return BoardSummary(
        path=path,
        sport=str(payload["sport"]) if payload.get("sport") else None,
        slate_key=str(
            payload.get("slate_key")
            or payload.get("slate_or_game_id")
            or payload.get("slate_date")
            or ""
        )
        or None,
        label=label,
        player_count=len(normalized),
        top_players=tuple(normalized[:top_n]),
    )


def load_board_summary(path: Path, *, top_n: int = 15) -> BoardSummary:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"hv_board_must_be_object:{path}")
    return summarize_board_payload(raw, path=str(path), top_n=top_n)


def discover_board_paths(root: Path) -> list[Path]:
    """Find hv_board.json / total_value_leaderboard.json under a root."""

    root = Path(root)
    if not root.is_dir():
        return []
    found: list[Path] = []
    for name in ("hv_board.json", "total_value_leaderboard.json"):
        found.extend(sorted(root.rglob(name)))
    # de-dupe while preserving order
    seen: set[Path] = set()
    out: list[Path] = []
    for path in found:
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out
