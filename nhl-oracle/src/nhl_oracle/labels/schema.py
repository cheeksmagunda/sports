"""Real ``value`` label schema for NHL chronological baselines.

Real Sports player ``value`` is a **label** after finalization, never a
same-slate live feature. The train + backtest product target is the Highest
Total Value board (``highestBoostedValuePlayers``) when contest data exists
(#535 / #453). Fit only on matured labels relative to the evaluation block
(walk-forward by season). Observation only; no contest entry.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

LabelRole = Literal["train_label", "live_forbidden_feature"]

# Canonical Real Sports draftStats section for train / backtest (#535).
TRAINING_LABEL_SECTION = "highestBoostedValuePlayers"


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
    section: str | None = None
    contest_id: int | None = None
    card_boost: float | None = None
    label_kind: str | None = None

    def __post_init__(self) -> None:
        if self.player_id <= 0:
            raise ValueError("player_id_must_be_positive")
        if self.game_id <= 0:
            raise ValueError("game_id_must_be_positive")
        if self.season <= 0:
            raise ValueError("season_must_be_positive")
        if not self.position.strip():
            raise ValueError("position_required")
        # Reject NaN / non-finite without coercing missing values to 0.0.
        if self.value != self.value:  # NaN
            raise ValueError("value_must_be_finite")
        if self.value == float("inf") or self.value == float("-inf"):
            raise ValueError("value_must_be_finite")
        if self.card_boost is not None and self.card_boost < 0:
            raise ValueError("card_boost_must_be_non_negative")
        if self.contest_id is not None and self.contest_id <= 0:
            raise ValueError("contest_id_must_be_positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


LABEL_FIELD_DOCS: dict[str, str] = {
    "player_id": "Real Sports player id (opaque; schema.org Person identifier).",
    "game_id": "Real Sports game id (schema.org SportsEvent identifier).",
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
    "section": (
        f"draftStats sectionName; train target is {TRAINING_LABEL_SECTION} "
        "when contest HV data exists."
    ),
    "contest_id": "Real Sports contest id when the label came from contest stats.",
    "card_boost": (
        "Card multiplierBonus when known; forced 0 under the all-teams-played "
        "zero-boost gate. Null means unknown (never silently treated as 0 for "
        "boost-cleared eras)."
    ),
    "label_kind": "high_total_value_board or raw_highest_score_pre_boost ladder rung.",
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
        "version": 2,
        "target": "value",
        "train_label_section": TRAINING_LABEL_SECTION,
        "fields": dict(LABEL_FIELD_DOCS),
        "train": {
            "may_use": [
                "finalized_real_value_as_label",
                f"draftStats.sectionName={TRAINING_LABEL_SECTION}",
            ],
            "must_not_use": ["winning_drafts", "contest_leaderboards_as_fit_target"],
            "fit_rule": (
                "Walk-forward by season: train only on seasons strictly earlier "
                "than the evaluation season; never peek at same-season labels. "
                f"Prefer {TRAINING_LABEL_SECTION} when contest data exists."
            ),
            "boost_note": (
                "Pre-boost regime (none) until every NHL team has played; "
                "do not treat card boosts as labels or live features before that."
            ),
            "corpus_gap": (
                "When durable RS contest HV ingest is missing, report "
                "HvCorpusGap rather than inventing labels (see labels.hv)."
            ),
        },
        "live": {
            "blacklist": list(LIVE_FEATURE_BLACKLIST),
            "contest_entry": False,
        },
        "observation_only": True,
        "goalie_eligible": True,
        "entity_ids": {
            "player_id": "schema.org/Person identifier (Real Sports opaque int)",
            "game_id": "schema.org/SportsEvent identifier",
            "contest_id": "schema.org/SportsEvent identifier (contest slate)",
            "team_id": "schema.org/SportsTeam identifier when present",
        },
    }
