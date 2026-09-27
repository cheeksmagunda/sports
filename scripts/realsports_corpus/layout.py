"""Explicit on-disk layout for Real Sports corpus kinds (#526).

Kind-first paths match cheeksmagunda/sports-realsports-corpus:

  {kind}/{sport}/{year}/slate_{YYYY-MM-DD}/…

Operator sequencing lock: capture these kinds before any Ollama helper.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Sport = Literal["wnba", "nfl", "nba", "nhl"]

SPORTS: tuple[Sport, ...] = ("wnba", "nfl", "nba", "nhl")

VariableFamily = Literal[
    "players",
    "team_weights",
    "lineups",
    "slate_rosters",
    "averages",
    "combined_stats",
    "recorded_states",
    "total_value_leaderboards",
    "matchups",
    "draft_stats_all_sections",
    "feeds",
]

REQUIRED_VARIABLE_FAMILIES: tuple[VariableFamily, ...] = (
    "players",
    "team_weights",
    "lineups",
    "slate_rosters",
    "averages",
    "combined_stats",
    "recorded_states",
    "total_value_leaderboards",
    "matchups",
    "draft_stats_all_sections",
    "feeds",
)

FAMILY_NOTES: dict[VariableFamily, str] = {
    "players": "Player cards / identity rows.",
    "team_weights": "Per-team weighting / squad weights.",
    "lineups": "Finisher and field lineups.",
    "slate_rosters": "Per-slate draftable pool.",
    "averages": "Season or trailing averages.",
    "combined_stats": "Combined / box score stats.",
    "recorded_states": "Point-in-time platform snapshots.",
    "total_value_leaderboards": "Highest value / Total Value Daily Leaderboard.",
    "matchups": "Game matchups and opponent context.",
    "draft_stats_all_sections": "Full draftStats section dumps.",
    "feeds": "Game / contest feed payloads.",
}


@dataclass(frozen=True)
class SlateKey:
    sport: Sport
    year: int
    slate_date: str  # YYYY-MM-DD


def kind_root(corpus_root: Path, kind: VariableFamily) -> Path:
    return Path(corpus_root) / kind


def family_dir(corpus_root: Path, key: SlateKey, family: VariableFamily) -> Path:
    return (
        kind_root(corpus_root, family)
        / key.sport
        / str(key.year)
        / f"slate_{key.slate_date}"
    )


def ensure_kind_roots(corpus_root: Path) -> dict[VariableFamily, Path]:
    """Ensure every top-level kind directory exists (corpus repo scaffold)."""

    created: dict[VariableFamily, Path] = {}
    root = Path(corpus_root)
    root.mkdir(parents=True, exist_ok=True)
    for family in REQUIRED_VARIABLE_FAMILIES:
        path = kind_root(root, family)
        path.mkdir(parents=True, exist_ok=True)
        keep = path / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
        created[family] = path.resolve()
    return created


def ensure_slate_layout(corpus_root: Path, key: SlateKey) -> dict[VariableFamily, Path]:
    """Create every required kind directory for one slate."""

    created: dict[VariableFamily, Path] = {}
    for family in REQUIRED_VARIABLE_FAMILIES:
        path = family_dir(corpus_root, key, family)
        path.mkdir(parents=True, exist_ok=True)
        keep = path / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
        created[family] = path.resolve()
    return created


def layout_tree_doc() -> str:
    lines = ["```"]
    for family in REQUIRED_VARIABLE_FAMILIES:
        lines.append(f"{family}/")
        lines.append(f"  # {FAMILY_NOTES[family]}")
    lines.extend(
        [
            "coverage_manifest.json",
            "```",
        ]
    )
    return "\n".join(lines)
