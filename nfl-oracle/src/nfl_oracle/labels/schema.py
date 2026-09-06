"""Real ``value`` label schema and train/live clock boundaries.

Corpus G ``playerBoxScores[].value`` is the realized Real Sports player value.
It is a **label** after finalization, never a same-slate live feature.

Clock roles (see ``nfl_oracle.ingest.clocks``):

- ``event_time``: kickoff / game event.
- ``source_available_at``: provider finalization clock when known; null on many
  older seasons (do not invent availability).
- ``captured_at``: when nfl-oracle wrote the redacted artifact.
- ``decision_at``: live/prospective pre-lock wall clock. Null on historical
  Corpus G backfill. Live features require
  ``source_available_at`` and ``captured_at`` <= ``decision_at``.

Train vs live:

- **Train / research**: attach finalized Real ``value`` as the supervision
  target for earlier seasons/games. Fit only on records whose labels are
  matured relative to the evaluation block (walk-forward by season here).
- **Live / shadow**: do not use same-slate final value, bonus, ranks,
  snap counts, TDs, ownership, or post-lock boxes as features.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

LabelRole = Literal["train_label", "live_forbidden_feature"]


@dataclass(frozen=True)
class ValueLabel:
    """One player-game Real ``value`` label row extracted from Corpus G."""

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
    corpus: str = "G"
    source_endpoint: str = "stats"
    did_not_play: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


LABEL_FIELD_DOCS: dict[str, str] = {
    "player_id": "Real Sports player id from playerBoxScores.playerId.",
    "game_id": "Real Sports game id (Corpus G path key).",
    "season": "NFL season year from feed.game.season / path.",
    "position": "Box-score position string (QB, RB, WR, TE, ...).",
    "value": "Realized Real Sports value; train/research label only.",
    "team_id": "Optional Real Sports team id when present.",
    "event_time": "Game kickoff clock from provider game.dateTime.",
    "source_available_at": (
        "Provider finalization clock when known; null if unknown (common on older seasons)."
    ),
    "captured_at": "When nfl-oracle persisted the redacted stats artifact.",
    "decision_at": (
        "Live decision wall-clock (pre-lock). Null on Corpus G backfill; "
        "required on live/shadow decision snapshots."
    ),
    "label_role": "train_label for matured finals; never a live feature.",
    "corpus": "Always G for archive game boxes in this package.",
    "source_endpoint": "stats (playerBoxScores), not contest entries.",
    "did_not_play": "Optional provider flag when present on the box row.",
}


LIVE_FEATURE_BLACKLIST: tuple[str, ...] = (
    "same_slate_final_value",
    "same_slate_bonus",
    "same_slate_ranks",
    "same_slate_snap_counts",
    "same_slate_tds",
    "same_slate_ownership",
    "post_lock_boxes",
    "post_lock_plays",
)


def schema_document() -> dict[str, Any]:
    """Machine-readable schema + clock contract for docs/CLI (no secrets)."""

    return {
        "name": "real_value_label",
        "version": 1,
        "target": "value",
        "fields": dict(LABEL_FIELD_DOCS),
        "train": {
            "may_use": ["finalized_real_value_as_label"],
            "fit_rule": (
                "Walk-forward by season: train only on seasons strictly earlier "
                "than the evaluation season; never peek at same-season anchors."
            ),
            "clock_note": (
                "Labels come from post-game stats. Prefer source_available_at when "
                "present; historical backfill may still label with decision_at=null."
            ),
        },
        "live": {
            "features_require": ("source_available_at and captured_at <= decision_at (pre-lock)."),
            "blacklist": list(LIVE_FEATURE_BLACKLIST),
            "contest_entry": False,
        },
        "observation_only": True,
    }


def is_live_feature_allowed(*, decision_at: str | None) -> bool:
    """Same-slate Real value is never a live feature, regardless of clocks."""

    del decision_at
    return False


def is_train_label_row(label: ValueLabel) -> bool:
    """Historical Corpus G rows with finite value are train labels."""

    return label.label_role == "train_label" and label.decision_at is None
