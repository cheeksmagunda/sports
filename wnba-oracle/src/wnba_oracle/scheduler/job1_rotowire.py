"""Job 1 RotoWire identity matching and injury-status interpretation.

Extracted from job1.py. Owns the cross-source name normalization that
joins RotoWire lineup entries to Real Sports pool rows, plus the shared
"what counts as OUT" token set. Pure logic: no DB, no HTTP.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from wnba_oracle.ingest.rotowire import LineupEntry

# RotoWire status strings that mean "do not draft" -- matches the same
# token set used by features/injury_cascade.py so the two paths agree on
# what "OUT" means.
_OUT_STATUS_TOKENS = {"OUT", "IL", "INJ", "INACTIVE", "NA"}


def _normalize_name(name: str) -> str:
    """Case-fold + strip suffixes for RotoWire <-> Real Sports name matching.

    Beyond case + Jr./Sr./III suffixes, folds the three cross-source spelling
    hazards that silently mislabel starters as bench (the 2026-07-07 PHO
    slot-1 hole: RotoWire "M. Akoa-Makani" vs Real Sports "Monique Akoa
    Makani" missed BOTH join keys, so an expected starter took the
    unknown-role fade):
      - diacritics:  "Noémie" == "Noemie" (NFKD ASCII fold)
      - hyphens:     "Akoa-Makani" == "Akoa Makani" (split BEFORE stripping
        punctuation so double surnames keep a last-token join key)
      - apostrophes/periods: "A'ja" == "Aja", "M." == "M"
    """
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    folded = "".join(c for c in nfkd if not unicodedata.combining(c))
    folded = folded.replace("-", " ").replace("/", " ")
    cleaned = "".join(c for c in folded if c.isalnum() or c.isspace())
    parts = [p for p in cleaned.strip().split() if p]
    suffixes = {"jr", "sr", "ii", "iii", "iv"}
    parts = [p for p in parts if p.lower() not in suffixes]
    return " ".join(parts).lower()


def _name_keys(name: str) -> tuple[str, str]:
    """Return (full_norm, initial_norm) join keys for a player name.

    full_norm    = the case/suffix-normalized full name ('cecilia zandalasini').
    initial_norm = first-initial + last name ('c zandalasini').

    Both 'C. Zandalasini' (RotoWire often abbreviates the visiting team's first
    names) and 'Cecilia Zandalasini' (Real Sports' full names) collapse to the
    same initial_norm, so the initial key bridges the two sources when the full
    names differ. The exact key is still tried first to avoid first-initial +
    last-name collisions between two different players on the same team.
    """
    norm = _normalize_name(name)
    parts = norm.split()
    if len(parts) >= 2:
        initial = parts[0].rstrip(".")[:1]
        return norm, f"{initial} {parts[-1]}"
    return norm, norm


@dataclass(frozen=True)
class RotowireIndex:
    """(team, name) -> LineupEntry lookup with an abbreviated-name fallback."""

    exact: dict[tuple[str, str], LineupEntry]
    by_initial: dict[tuple[str, str], LineupEntry]

    def get(self, team: str, name: str) -> LineupEntry | None:
        team_u = team.upper()
        full_norm, initial_norm = _name_keys(name)
        hit = self.exact.get((team_u, full_norm))
        if hit is not None:
            return hit
        return self.by_initial.get((team_u, initial_norm))

    def __contains__(self, key: tuple[str, str]) -> bool:
        # Back-compat for `(team, normalized_name) in idx` callers/tests.
        return key in self.exact


def _index_rotowire(entries: list[LineupEntry]) -> RotowireIndex:
    """Build a RotowireIndex so Real Sports pool rows enrich in O(1).

    Keys each entry under both the exact normalized full name and the
    first-initial + last-name fallback so abbreviated RotoWire names still
    match Real Sports' full names (D100 fix)."""
    exact: dict[tuple[str, str], LineupEntry] = {}
    by_initial: dict[tuple[str, str], LineupEntry] = {}
    for e in entries:
        team = e.team.upper()
        full_norm, initial_norm = _name_keys(e.player_name)
        exact[(team, full_norm)] = e
        # First write wins on the initial key so a later collision (two players,
        # same team + initial + last name) can't clobber the first; the exact
        # key still disambiguates when the full name is present.
        by_initial.setdefault((team, initial_norm), e)
    return RotowireIndex(exact=exact, by_initial=by_initial)


def is_out_status(status: str | None) -> bool:
    """True iff RotoWire's status token marks the player as a confirmed
    non-draft. Used by both job1 (when persisting features_json) and job2
    (when filtering the optimizer pool)."""
    if not status:
        return False
    upper = status.strip().upper()
    return any(tok in upper for tok in _OUT_STATUS_TOKENS)


def rotowire_patch(rw: LineupEntry) -> dict:
    """The RotoWire-authoritative subset of features_json: starter slot +
    confirmation, and the injury status ONLY when RotoWire has a fresh one
    (so a Real-Sports-sourced OUT is never wiped by a blank RotoWire row)."""
    patch: dict[str, object] = {
        "is_starter": int(1 <= rw.starter_slot <= 5),
        "starter_slot": int(rw.starter_slot),
        "rotowire_confirmed": int(bool(rw.confirmed)),
    }
    if rw.injury_status:
        patch["injury_status"] = rw.injury_status
        patch["is_out"] = int(is_out_status(rw.injury_status))
    return patch
