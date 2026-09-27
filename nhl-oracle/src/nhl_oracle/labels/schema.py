"""Real ``value`` label schema for NHL chronological baselines.

Real Sports player ``value`` is a **label** after finalization, never a
same-slate live feature. Fit only on matured labels relative to the
evaluation block (walk-forward by season). Observation only; no contest entry.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

LabelRole = Literal["train_label", "live_forbidden_feature"]


@dataclass(frozen=True)
class ValueLabel:
    """One player-game Real ``value`` label row for NHL research baselines."""

    player_id: int
    game_id: int
    season: int
    position: str
    value: float
    team_id: int | None = None
    event_time: str | None = None
    source_available_at: str | None = None
    captured_at: str | None = None
    decision_at: str | None = None
    label_role: LabelRole = "train_label"
    source_endpoint: str = "stats"
    did_not_play: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


LABEL_FIELD_DOCS: dict[str, str] = {
    "player_id": "Real Sports player id.",
    "game_id": "Real Sports game id.",
    "season": "NHL season start year (e.g. 2025 for 2025-26).",
    "position": "Box/card position string (C, LW, RW, D, G, ...).",
    "value": "Realized Real Sports value; train/research label only.",
    "team_id": "Optional Real Sports team id when present.",
    "event_time": "Game start clock when known.",
    "source_available_at": "Provider finalization clock when known; null if unknown.",
    "captured_at": "When nhl-oracle persisted the redacted artifact.",
    "decision_at": (
        "Live decision wall-clock (pre-lock). Null on historical backfill; "
        "required on live/shadow decision snapshots."
    ),
    "label_role": "train_label for matured finals; never a live feature.",
    "source_endpoint": "stats / player cards, not contest entries.",
    "did_not_play": "Optional provider flag when present.",
}


LIVE_FEATURE_BLACKLIST: tuple[str, ...] = (
    "same_slate_final_value",
    "same_slate_bonus",
    "same_slate_ranks",
    "same_slate_ownership",
    "post_lock_boxes",
    "card_boost_as_label",
)


def schema_document() -> dict[str, Any]:
    """Machine-readable schema + clock contract (no secrets)."""

    return {
        "name": "nhl_real_value_label",
        "version": 1,
        "target": "value",
        "fields": dict(LABEL_FIELD_DOCS),
        "train": {
            "may_use": ["finalized_real_value_as_label"],
            "fit_rule": (
                "Walk-forward by season: train only on seasons strictly earlier "
                "than the evaluation season; never peek at same-season labels."
            ),
            "boost_note": (
                "Hard gate: boost_regime=none until every NHL team has >=1 GP "
                "this season. The gap between early games starting (when boost "
                "fields may tempt the field) and every team completing one game "
                "is the edge - keep none and exploit mispricing; do not treat "
                "card boosts as labels or live features before that milestone."
            ),
        },
        "live": {
            "blacklist": list(LIVE_FEATURE_BLACKLIST),
            "contest_entry": False,
        },
        "observation_only": True,
        "goalie_eligible": True,
    }
