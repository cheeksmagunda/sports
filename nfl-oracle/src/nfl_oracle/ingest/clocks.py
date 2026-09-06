"""Train/live information clocks for Corpus G provenance.

Playbook fields (NFL strategy doc + Slice 1 train/live boundaries):

- ``event_time``: when the game/event occurred (kickoff / ``game.dateTime``).
  Applies to every Corpus G game artifact.
- ``source_available_at``: earliest observed time the *source* made this
  payload state available. For finalized boxes/value we prefer
  ``postProcessedAt``, then ``gameEndDateTime``, then ``closedAt``. When
  none are present (common on older seasons), leave null rather than
  inventing availability — do not backdate finals to kickoff.
- ``captured_at``: when nfl-oracle fetched and persisted the redacted
  payload (always set on provenance sidecars).
- ``decision_at``: wall-clock of a live/prospective decision (pre-lock).
  Not set during historical Corpus G backfill; reserved for live/shadow
  decision snapshots. Live features require
  ``source_available_at`` and ``captured_at`` ≤ ``decision_at``.

Training may attach post-game Real ``value`` as labels after finalization.
Live decisions must not use same-slate finals / bonus / ranks / ownership
as features.
"""

from __future__ import annotations

from typing import Any


def _as_iso(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def event_time_from_game(game: dict[str, Any] | None) -> str | None:
    """Kickoff / event time from a Real Sports ``game`` object."""

    if not isinstance(game, dict):
        return None
    return _as_iso(game.get("dateTime")) or _as_iso(game.get("day"))


def source_available_at_from_game(game: dict[str, Any] | None) -> str | None:
    """Best-effort finalization / availability timestamp from ``game``.

    Prefer post-process completion over end/close. Returns None when the
    provider does not expose a finalization clock (do not substitute kickoff).
    """

    if not isinstance(game, dict):
        return None
    for key in ("postProcessedAt", "gameEndDateTime", "closedAt"):
        stamp = _as_iso(game.get(key))
        if stamp is not None:
            return stamp
    return None


def clocks_for_game(
    game: dict[str, Any] | None,
    *,
    captured_at: str | None = None,
    decision_at: str | None = None,
) -> dict[str, str | None]:
    """Build the four-field clock map for manifests / docs consumers."""

    return {
        "event_time": event_time_from_game(game),
        "source_available_at": source_available_at_from_game(game),
        "captured_at": _as_iso(captured_at),
        "decision_at": _as_iso(decision_at),
    }


def clock_field_docs() -> dict[str, str]:
    """Short applicability notes safe to embed in manifests (no secrets)."""

    return {
        "event_time": "Game kickoff / event time from provider game.dateTime (or day).",
        "source_available_at": (
            "Provider finalization clock when present "
            "(postProcessedAt > gameEndDateTime > closedAt); null if unknown."
        ),
        "captured_at": "Wall clock when nfl-oracle fetched and wrote the redacted artifact.",
        "decision_at": (
            "Live/prospective decision time (pre-lock). Null on historical Corpus G "
            "backfill; required on live decision snapshots."
        ),
    }
