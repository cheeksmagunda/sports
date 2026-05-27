"""Real Sports contest /stats endpoint adapter.

Pulls per-player `real_score` (the training label) + `card_boost` for a
single contest. Used by the live slate-close collector and (where the
platform permits) by the historical backfill.

Endpoint: GET /games/playerratingcontest/{id}/stats
Response shape (post-finalization):

    {
      "contest": {"id": ..., "sport": "wnba", "day": "YYYY-MM-DD", "isFinalized": true},
      "draftStats": [
        {"sectionName": "highestBoostedValuePlayers",
         "players": [
           {"player": {"id": ..., "displayName": ...},
            "team": {"key": ...},
            "multiplierBonus": float,         # card_boost
            "value": "string",                 # raw per-slate real_score
            "displayStats": [{"label": ..., "value": ...}]}
         ]},
        ...
      ]
    }

Same DRAFT_STATS sections as the MLB precedent. Pregame contests have
`draftStats == []`; the collector skips them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import httpx
import polars as pl

from wnba_oracle.common.logging import get_logger
from wnba_oracle.ingest.realsports import (
    BASE,
    PlatformAuthRequired,
    RequestHeaders,
    _http_headers,
)

log = get_logger("oracle.ingest.contest_stats")

DRAFT_STATS_SECTIONS = {
    "highestBoostedValuePlayers",
    "popularPlayers",
    "mostCommon3xPlayers",
}


class ContestUnavailable(RuntimeError):
    """Contest endpoint returned 404 / empty / forbidden. Caller should
    skip the slate, not halt the whole backfill."""


@dataclass(frozen=True)
class ContestLabel:
    """One per-slate per-player training label."""

    contest_id: int
    slate_date: str  # YYYY-MM-DD
    section: str
    platform_player_id: int
    display_name: str
    team_key: str
    card_boost: float
    drafts: int | None
    real_score: float | None


def _parse_drafts(raw: object) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    s = str(raw).strip().lower()
    if not s:
        return None
    if s.endswith("k"):
        try:
            return round(float(s[:-1]) * 1000)
        except ValueError:
            return None
    try:
        return int(s)
    except ValueError:
        return None


def _parse_real_score(raw: object) -> float | None:
    """Per-slate real_score - ingested verbatim from `player.value`, never
    computed or approximated."""
    if raw is None:
        return None
    s = str(raw).strip().replace("+", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_contest_stats(
    contest_id: int,
    headers: RequestHeaders,
    client: httpx.Client,
    *,
    refresh_headers: Callable[[], RequestHeaders] | None = None,
) -> list[ContestLabel]:
    """Synchronous fetch + parse. Returns per-player labels for the contest.

    On 401, if a `refresh_headers` callback is supplied, call it once,
    re-build the header dict, and retry. Subsequent 401 raises
    `PlatformAuthRequired`. 404 raises `ContestUnavailable` (the caller
    skips the slate rather than halting the backfill).
    """
    h = _http_headers(headers)
    url = f"{BASE}/games/playerratingcontest/{contest_id}/stats"
    log.info("contest_stats_fetch", contest_id=contest_id)
    refreshed = False
    while True:
        r = client.get(url, headers=h, timeout=20.0)
        if r.status_code == 401 and refresh_headers is not None and not refreshed:
            log.info("contest_stats_401_refresh", contest_id=contest_id)
            h = _http_headers(refresh_headers())
            refreshed = True
            continue
        if r.status_code == 401:
            raise PlatformAuthRequired(f"401 on {url}")
        if r.status_code == 404:
            raise ContestUnavailable(f"404 on {url}")
        r.raise_for_status()
        break
    body = r.json() or {}
    contest = body.get("contest") or {}
    if contest.get("sport") != "wnba":
        raise ContestUnavailable(
            f"contest {contest_id} sport={contest.get('sport')} (expected wnba)"
        )
    slate_date = str(contest.get("day", ""))
    sections = body.get("draftStats") or []
    out: list[ContestLabel] = []
    for sec in sections:
        sec_name = sec.get("sectionName")
        if sec_name not in DRAFT_STATS_SECTIONS:
            continue
        for entry in sec.get("players") or []:
            pl_obj = entry.get("player") or {}
            tm_obj = entry.get("team") or {}
            pid = pl_obj.get("id")
            tkey = tm_obj.get("key")
            if pid is None or not tkey:
                continue
            display_stats = {
                x.get("label"): x.get("value") for x in (entry.get("displayStats") or [])
            }
            out.append(
                ContestLabel(
                    contest_id=int(contest_id),
                    slate_date=slate_date,
                    section=str(sec_name),
                    platform_player_id=int(pid),
                    display_name=str(pl_obj.get("displayName", "")).strip(),
                    team_key=str(tkey).strip().upper(),
                    card_boost=float(entry.get("multiplierBonus", 0.0)),
                    drafts=_parse_drafts(display_stats.get("Drafts")),
                    real_score=_parse_real_score(entry.get("value")),
                )
            )
    return out


def labels_to_polars(labels: list[ContestLabel]) -> pl.DataFrame:
    return pl.from_dicts([label.__dict__ for label in labels]) if labels else pl.DataFrame()


def dedupe_by_player(labels: list[ContestLabel]) -> list[ContestLabel]:
    """A player can appear in multiple draftStats sections (same boost +
    real_score). Keep the first observed row per platform_player_id."""
    seen: set[int] = set()
    out: list[ContestLabel] = []
    for label in labels:
        if label.platform_player_id in seen:
            continue
        seen.add(label.platform_player_id)
        out.append(label)
    return out
