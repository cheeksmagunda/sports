"""Extract Real ``value`` labels from Corpus G on-disk artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nfl_oracle.labels.schema import ValueLabel


def _parse_float(raw: Any) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _parse_int(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _clocks_from_manifest(manifest: dict[str, Any] | None) -> dict[str, str | None]:
    clocks = (manifest or {}).get("clocks") if isinstance(manifest, dict) else None
    if not isinstance(clocks, dict):
        clocks = {}
    return {
        "event_time": clocks.get("event_time"),
        "source_available_at": clocks.get("source_available_at"),
        "captured_at": clocks.get("captured_at"),
        "decision_at": clocks.get("decision_at"),
    }


def labels_from_stats_payload(
    *,
    stats: dict[str, Any],
    game_id: int,
    season: int,
    clocks: dict[str, str | None] | None = None,
) -> list[ValueLabel]:
    """Build label rows from a redacted stats payload."""

    clocks = clocks or {}
    out: list[ValueLabel] = []
    boxes = list(stats.get("playerBoxScores") or [])
    for row in boxes:
        if not isinstance(row, dict):
            continue
        value = _parse_float(row.get("value"))
        if value is None:
            continue
        player_id = _parse_int(row.get("playerId"))
        if player_id is None:
            continue
        position_raw = row.get("position")
        position = str(position_raw).strip().upper() if position_raw else "UNK"
        if not position:
            position = "UNK"
        dnp = row.get("didNotPlay")
        did_not_play: bool | None
        if isinstance(dnp, bool):
            did_not_play = dnp
        else:
            did_not_play = None
        out.append(
            ValueLabel(
                player_id=player_id,
                game_id=game_id,
                season=season,
                position=position,
                value=value,
                team_id=_parse_int(row.get("teamId")),
                event_time=clocks.get("event_time"),
                source_available_at=clocks.get("source_available_at"),
                captured_at=clocks.get("captured_at"),
                decision_at=clocks.get("decision_at"),
                did_not_play=did_not_play,
            )
        )
    return out


def load_labels_from_corpus_root(root: Path | str) -> list[ValueLabel]:
    """Load all value labels under a Corpus G raw root.

    Expected layout: ``{root}/{season}/{game_id}/stats.json`` with optional
    ``manifest.json`` for clocks. Missing or unreadable files are skipped.
    """

    root_path = Path(root)
    if not root_path.is_dir():
        return []
    labels: list[ValueLabel] = []
    for season_dir in sorted(p for p in root_path.iterdir() if p.is_dir()):
        season = _parse_int(season_dir.name)
        if season is None:
            continue
        for game_dir in sorted(p for p in season_dir.iterdir() if p.is_dir()):
            game_id = _parse_int(game_dir.name)
            if game_id is None:
                continue
            stats_path = game_dir / "stats.json"
            if not stats_path.is_file():
                continue
            try:
                stats = json.loads(stats_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(stats, dict):
                continue
            manifest: dict[str, Any] | None = None
            manifest_path = game_dir / "manifest.json"
            if manifest_path.is_file():
                try:
                    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        manifest = loaded
                except (OSError, json.JSONDecodeError):
                    manifest = None
            clocks = _clocks_from_manifest(manifest)
            labels.extend(
                labels_from_stats_payload(
                    stats=stats,
                    game_id=game_id,
                    season=season,
                    clocks=clocks,
                )
            )
    return labels
