"""Real Sports contest endpoint adapters: /stats + /entries.

Two endpoints share the same auth flow:

1. `fetch_contest_stats` -> GET /games/playerratingcontest/{id}/stats

   Per-player aggregated stats across three sections
   (highestBoostedValuePlayers, popularPlayers, mostCommon3xPlayers). One
   row per (contest, player). Shape:

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

2. `fetch_contest_entries` -> GET /games/playerratingcontest/{id}/entries
   ?contestType=sport&isGuillotine=false

   Top-20 finishers with their full lineups (each player's chosen
   multiplier + the per-player real_score that was realized). One row per
   (contest, entry). The `contestType=sport&isGuillotine=false` params
   are mandatory; omitting them returns a stale ncaam stub regardless of
   contest id.

Both endpoints share auth (real-request-token + real-auth-info captured
via Playwright). Pregame contests have `draftStats == []` and `entries == []`;
collectors skip them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import httpx

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


def _player_display_name(pl_obj: dict) -> str:
    """Resolve a player's display name from a contest `player` object.

    Mirrors the pool parser's D49 fallback: the Real Sports API has been
    observed to return an empty ``displayName`` while ``firstName`` /
    ``lastName`` stay populated. Reading ``displayName`` alone here would
    silently emit empty ``slate_labels.display_name`` rows, which is the
    fallback source the live freeze leans on. Fall back to
    ``firstName + lastName`` so the name source stays trustworthy."""
    dn = str(pl_obj.get("displayName", "") or "").strip()
    if dn:
        return dn
    first = str(pl_obj.get("firstName", "") or "").strip()
    last = str(pl_obj.get("lastName", "") or "").strip()
    return f"{first} {last}".strip()


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
    import time as _time

    backoff_429 = 0
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
        if r.status_code == 403:
            # Real Sports returns 403 on contests not visible to this account
            # (older seasons sometimes), or as a transient rate-limit signal.
            # Treat as unavailable so the backfill walker skips and continues.
            raise ContestUnavailable(f"403 on {url}")
        if r.status_code == 429:
            backoff_429 += 1
            if backoff_429 > 3:
                raise ContestUnavailable(f"429 on {url} after {backoff_429} retries")
            sleep_s = min(30, 2**backoff_429)
            log.warning("contest_stats_429_backoff", contest_id=contest_id, sleep_s=sleep_s)
            _time.sleep(sleep_s)
            continue
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
    # D85: surface sections we silently drop. slate_labels only covers the
    # three known sections (~30 players/slate); if the platform ever ships
    # a fuller section this log line is how we find out.
    unknown_sections = [
        str(s.get("sectionName"))
        for s in sections
        if s.get("sectionName") not in DRAFT_STATS_SECTIONS
    ]
    if unknown_sections:
        log.info(
            "contest_stats_unknown_sections",
            contest_id=contest_id,
            sections=unknown_sections,
        )
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
                    display_name=_player_display_name(pl_obj),
                    team_key=str(tkey).strip().upper(),
                    card_boost=float(entry.get("multiplierBonus", 0.0)),
                    drafts=_parse_drafts(display_stats.get("Drafts")),
                    real_score=_parse_real_score(entry.get("value")),
                )
            )
    return out


@dataclass(frozen=True)
class LeaderboardEntry:
    """One top-N finisher's lineup for a single contest.

    `lineup` is the raw 5-player payload from `additionalInfo.lineup` — each
    player dict carries `playerId`, `multiplier` (the user's chosen
    multiplier, NOT card_boost), `value` (the realized per-slate real_score
    as a string), `score` (multiplier * value), plus display metadata. We
    preserve the API shape verbatim per Hard Rule 7; consumers do their own
    field extraction.
    """

    contest_id: int
    slate_date: str
    entry_id: int
    rank: int
    paged_rank: int
    user_id: str
    score: float
    lineup: list[dict[str, object]]
    num_brawlers: int | None


def fetch_contest_entries(
    contest_id: int,
    headers: RequestHeaders,
    client: httpx.Client,
    *,
    refresh_headers: Callable[[], RequestHeaders] | None = None,
) -> list[LeaderboardEntry]:
    """Synchronous fetch of top-20 leaderboard entries for a single contest.

    Returns the parsed entries (one per finisher). The platform truncates
    to top 20 — `num_brawlers` on each entry carries the full contest
    entry count so consumers can reason about depth. 401 retries once via
    `refresh_headers`. 404 raises `ContestUnavailable` (skip the slate).
    Sport mismatch (cid resolved to a non-WNBA contest) raises
    `ContestUnavailable`.
    """
    h = _http_headers(headers)
    url = f"{BASE}/games/playerratingcontest/{contest_id}/entries"
    params = {"contestType": "sport", "isGuillotine": "false"}
    log.info("contest_entries_fetch", contest_id=contest_id)
    refreshed = False
    import time as _time

    backoff_429 = 0
    while True:
        r = client.get(url, headers=h, params=params, timeout=20.0)
        if r.status_code == 401 and refresh_headers is not None and not refreshed:
            log.info("contest_entries_401_refresh", contest_id=contest_id)
            h = _http_headers(refresh_headers())
            refreshed = True
            continue
        if r.status_code == 401:
            raise PlatformAuthRequired(f"401 on {url}")
        if r.status_code == 404:
            raise ContestUnavailable(f"404 on {url}")
        if r.status_code == 403:
            raise ContestUnavailable(f"403 on {url}")
        if r.status_code == 429:
            backoff_429 += 1
            if backoff_429 > 3:
                raise ContestUnavailable(f"429 on {url} after {backoff_429} retries")
            sleep_s = min(30, 2**backoff_429)
            log.warning("contest_entries_429_backoff", contest_id=contest_id, sleep_s=sleep_s)
            _time.sleep(sleep_s)
            continue
        r.raise_for_status()
        break
    body = r.json() or {}
    contest = body.get("contest") or {}
    if contest.get("sport") != "wnba":
        raise ContestUnavailable(
            f"contest {contest_id} sport={contest.get('sport')} (expected wnba)"
        )
    slate_date = str(contest.get("day", ""))
    num_brawlers = contest.get("numBrawlers")
    out: list[LeaderboardEntry] = []
    for e in body.get("entries") or []:
        eid = e.get("id")
        rank = e.get("rank")
        if eid is None or rank is None:
            continue
        try:
            score_f = float(e.get("score", 0.0))
        except (TypeError, ValueError):
            score_f = 0.0
        lineup = ((e.get("additionalInfo") or {}).get("lineup")) or []
        out.append(
            LeaderboardEntry(
                contest_id=int(contest_id),
                slate_date=slate_date,
                entry_id=int(eid),
                rank=int(rank),
                paged_rank=int(e.get("pagedRank", rank)),
                user_id=str(e.get("userId", "")),
                score=score_f,
                lineup=list(lineup),
                num_brawlers=int(num_brawlers) if num_brawlers is not None else None,
            )
        )
    return out


def labels_from_leaderboard_entries(
    entries: list[LeaderboardEntry],
) -> list[ContestLabel]:
    """D85: supplemental labels from top-20 finisher lineups.

    The /stats draftStats sections cover only ~30 highlighted players per
    slate; any pool player outside them (Loyd/Boston on 2026-06-08) loses
    their realized real_score forever. Leaderboard lineups carry the same
    per-player `value` verbatim from the platform, so harvest them as
    `section="leaderboard_lineup"`
    rows. Persistence uses DO NOTHING so these never clobber a canonical
    three-section row.

    card_boost reads `multiplierBonus` when the lineup dict carries it and
    falls back to 0.0; the section marker keeps the provenance explicit so
    training can treat the boost as unreliable for these rows. `multiplier`
    is the finisher's chosen slot multiplier, never a boost; it is ignored.
    """
    out: list[ContestLabel] = []
    for entry in entries:
        for p in entry.lineup:
            if not isinstance(p, dict):
                continue
            pid = p.get("playerId")
            if pid is None:
                continue
            team_obj = p.get("team")
            team_raw = p.get("teamKey") or (
                team_obj.get("key") if isinstance(team_obj, dict) else None
            )
            team_key = str(team_raw or "UNK").strip().upper() or "UNK"
            name = _player_display_name(p)
            try:
                boost = float(str(p.get("multiplierBonus", 0.0) or 0.0))
            except (TypeError, ValueError):
                boost = 0.0
            out.append(
                ContestLabel(
                    contest_id=entry.contest_id,
                    slate_date=entry.slate_date,
                    section="leaderboard_lineup",
                    platform_player_id=int(str(pid)),
                    display_name=name or f"Player {pid}",
                    team_key=team_key[:8],
                    card_boost=boost,
                    drafts=None,
                    real_score=_parse_real_score(p.get("value")),
                )
            )
    return dedupe_by_player(out)


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
