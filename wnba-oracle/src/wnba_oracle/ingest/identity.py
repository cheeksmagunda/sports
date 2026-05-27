"""Resolve Real Sports player_id → stats.wnba.com (`nba_api`) player_id.

Real Sports exposes `nbaId` on player rows when available; that's the
primary key when set. Fallback path: normalize name + team and match
against the nba_api static catalog.

Persistent overrides live in `data/identity_overrides.csv` (CSV with cols:
real_sports_id, wnba_player_id, full_name, team, notes). Use overrides
for cases the autoresolver misses (name format quirks, just-traded players,
etc.).
"""

from __future__ import annotations

import csv
import unicodedata
from pathlib import Path

import polars as pl

from wnba_oracle.common.logging import get_logger
from wnba_oracle.ingest.stats_wnba import get_wnba_static_players

log = get_logger("oracle.ingest.identity")

REPO_ROOT = Path(__file__).resolve().parents[3]
OVERRIDES_PATH = REPO_ROOT / "data" / "identity_overrides.csv"


def _normalize_name(n: str) -> str:
    """Lowercase, ASCII-fold, strip punctuation, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", n)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = "".join(c for c in ascii_only if c.isalnum() or c.isspace())
    return " ".join(cleaned.lower().split())


def load_overrides() -> dict[str, int]:
    """Return {real_sports_id: wnba_player_id}. Missing file returns {}."""
    if not OVERRIDES_PATH.exists():
        return {}
    out: dict[str, int] = {}
    with OVERRIDES_PATH.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            rsid = (row.get("real_sports_id") or "").strip()
            wpid = (row.get("wnba_player_id") or "").strip()
            if rsid and wpid:
                try:
                    out[rsid] = int(wpid)
                except ValueError:
                    continue
    return out


def build_resolver() -> Resolver:
    return Resolver()


class Resolver:
    """Resolves Real Sports player records to `nba_api` WNBA player ids."""

    def __init__(self) -> None:
        catalog = get_wnba_static_players()
        self._by_norm_name: dict[str, list[dict[str, object]]] = {}
        for p in catalog:
            key = _normalize_name(str(p.get("full_name", "")))
            if not key:
                continue
            self._by_norm_name.setdefault(key, []).append(p)
        self._overrides = load_overrides()
        log.info(
            "identity_resolver_loaded",
            n_catalog=len(catalog),
            n_overrides=len(self._overrides),
        )

    def resolve(
        self,
        real_sports_id: str,
        *,
        display_name: str,
        first_name: str = "",
        last_name: str = "",
        team: str = "",
        nba_id: int | None = None,
    ) -> int | None:
        # 1) explicit override
        if real_sports_id in self._overrides:
            return self._overrides[real_sports_id]
        # 2) trust the platform-provided nbaId when present
        if nba_id is not None:
            return int(nba_id)
        # 3) name match — try full, first+last, last alone
        candidates: list[str] = []
        if first_name and last_name:
            candidates.append(f"{first_name} {last_name}")
        if display_name:
            candidates.append(display_name)
            # Real Sports format is "F. Last"; expand if first_name available.
            if first_name and " " in display_name and "." in display_name.split()[0]:
                candidates.append(f"{first_name} {display_name.split()[-1]}")
        for name in candidates:
            matches = self._by_norm_name.get(_normalize_name(name), [])
            if len(matches) == 1:
                pid_val = matches[0].get("id")
                if isinstance(pid_val, int):
                    return pid_val
            # If multiple matches, the team disambiguates if we had it.
            # nba_api static catalog doesn't carry current team, so we have
            # to defer ambiguity to the override file.
        return None


def write_unresolved_log(
    rows: list[dict[str, object]],
    *,
    log_path: Path | None = None,
) -> None:
    """Persist unresolved (real_sports_id, name, team) tuples so the operator
    can add overrides. Append-only; deduplicated on read."""
    p = log_path or (REPO_ROOT / "data" / "identity_unresolved.csv")
    fields = ["real_sports_id", "display_name", "team"]
    new_file = not p.exists()
    with p.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def unresolved_to_polars(unresolved: list[dict[str, object]]) -> pl.DataFrame:
    return pl.from_dicts(unresolved) if unresolved else pl.DataFrame()
