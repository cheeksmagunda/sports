"""Turn saved Corpus C payloads into validated records.

Parsing is deliberately strict about the scoring law. Every saved human entry
carries ``value``, ``multiplier`` and ``score`` per card, so the additive law
``score = value * (slot_multiplier + card_boost)`` is not assumed here, it is
checked on every row by :class:`EntryLineupPick`. A contest whose entries fail
that check is a rule-era change and must surface, not be averaged in.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from nfl_oracle.contests.boosts import boost_from_multiplier, slot_multiplier_for
from nfl_oracle.contests.schema import (
    OBSERVED_SLOT_MULTIPLIERS,
    ContestRecord,
    DraftStatRow,
    EntryLineupPick,
    EntryRecord,
    PayoutTier,
    RaxPoolOption,
)
from nfl_oracle.contests.store import ContestStore


class ContestParseError(ValueError):
    """A saved payload does not match the contract this parser verifies."""


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and out not in (float("inf"), float("-inf")) else None


def _int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_contest_record(
    meta: Mapping[str, Any],
    *,
    draftinfo: Mapping[str, Any] | None = None,
    payoutinfo: Mapping[str, Any] | None = None,
    captured_at: datetime,
) -> ContestRecord:
    info = meta.get("info")
    if not isinstance(info, dict):
        raise ContestParseError("meta_missing_info")
    contest = info.get("contest")
    if not isinstance(contest, dict):
        raise ContestParseError("meta_missing_contest")
    rules = (draftinfo or {}).get("info") if isinstance(draftinfo, dict) else None
    multipliers = None
    if isinstance(rules, dict):
        raw = rules.get("defaultMultipliers")
        if isinstance(raw, list) and raw:
            multipliers = tuple(float(x) for x in raw)
    tiers: list[PayoutTier] = []
    if isinstance(payoutinfo, dict):
        items = (payoutinfo.get("info") or {}).get("payoutInfoItems")
        for item in items if isinstance(items, list) else []:
            amount = _float(item.get("prizeAmount"))
            if amount is not None and isinstance(item.get("rankDisplay"), str):
                tiers.append(PayoutTier(rank_display=item["rankDisplay"], prize_amount=amount))
    pools: list[RaxPoolOption] = []
    if isinstance(rules, dict):
        options = (rules.get("raxContestPoolDetails") or {}).get("options")
        for option in options if isinstance(options, list) else []:
            percent, payout = _float(option.get("percent")), _float(option.get("payout"))
            if percent and payout and isinstance(option.get("key"), str):
                wagers = option.get("wagerOptions")
                pools.append(
                    RaxPoolOption(
                        key=option["key"],
                        percent=percent,
                        payout_multiple=payout,
                        wager_options=tuple(int(w) for w in wagers if isinstance(w, int))
                        if isinstance(wagers, list)
                        else (),
                    )
                )
    size = _int((contest.get("additionalInfo") or {}).get("lineupSize")) or _int(
        (rules or {}).get("lineupSize")
    )
    return ContestRecord(
        contest_id=contest["id"],
        sport=contest.get("sport", "nfl"),
        day=contest["day"],
        end_day=contest.get("endDay") or contest["day"],
        season=_int(contest.get("season")),
        lineup_size=size or 5,
        slot_multipliers=multipliers or OBSERVED_SLOT_MULTIPLIERS,
        entrants=_int(contest.get("numBrawlers")) or 0,
        is_finalized=bool(contest.get("isFinalized")),
        is_locked=info.get("isLocked") if isinstance(info.get("isLocked"), bool) else None,
        comment_count=_int(contest.get("commentCount")),
        created_at=_dt(contest.get("createdAt")),
        processed_at=_dt(contest.get("processedAt")),
        game_id=_int(contest.get("gameId")),
        payout_tiers=tuple(tiers),
        rax_pools=tuple(pools),
        captured_at=captured_at,
    )


def parse_entries(
    entries_payload: Mapping[str, Any],
    *,
    contest_id: int,
    slot_multipliers: Sequence[float] = OBSERVED_SLOT_MULTIPLIERS,
) -> list[EntryRecord]:
    rows = entries_payload.get("entries")
    if not isinstance(rows, list):
        raise ContestParseError("entries_missing")
    out: list[EntryRecord] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        lineup = (row.get("additionalInfo") or {}).get("lineup")
        if not isinstance(lineup, list) or not lineup:
            continue
        picks: list[EntryLineupPick] = []
        for card in lineup:
            if not isinstance(card, dict):
                continue
            order = _int(card.get("order"))
            effective = _float(card.get("multiplier"))
            player_id = _int(card.get("playerId")) or _int(card.get("id"))
            if order is None or effective is None or player_id is None:
                raise ContestParseError("entry_card_incomplete")
            slot = order + 1
            slot_multiplier = slot_multiplier_for(slot, slot_multipliers)
            declared = _float(card.get("multiplierBonus"))
            recovered = boost_from_multiplier(effective, slot_multiplier)
            # Prefer the provider's own bonus, but only when it reconciles.
            boost = recovered if declared is None or abs(declared - recovered) > 0.05 else declared
            picks.append(
                EntryLineupPick(
                    player_id=player_id,
                    slot=slot,
                    slot_multiplier=slot_multiplier,
                    card_boost=boost,
                    effective_multiplier=round(slot_multiplier + boost, 6),
                    value=_float(card.get("value")),
                    score=_float(card.get("score")),
                    real_rank=_int(card.get("realRank")),
                    is_exact=card.get("isExact") if isinstance(card.get("isExact"), bool) else None,
                    team_id=_int(card.get("teamId")),
                    display_name=card.get("displayName")
                    if isinstance(card.get("displayName"), str)
                    else None,
                    injury_status=card.get("injuryStatus")
                    if isinstance(card.get("injuryStatus"), str)
                    else None,
                )
            )
        entry_id, rank = _int(row.get("id")), _int(row.get("rank"))
        if entry_id is None or rank is None:
            raise ContestParseError("entry_identity_missing")
        out.append(
            EntryRecord(
                contest_id=contest_id,
                entry_id=entry_id,
                rank=rank,
                score=_float(row.get("score")),
                payout=_float(row.get("payout")),
                wager=_float(row.get("wager")),
                entry_type=row.get("type") if isinstance(row.get("type"), str) else None,
                picks=tuple(picks),
            )
        )
    return out


def parse_draft_stats(stats_payload: Mapping[str, Any], *, contest_id: int) -> list[DraftStatRow]:
    sections = stats_payload.get("draftStats")
    if not isinstance(sections, list):
        raise ContestParseError("draft_stats_missing")
    out: list[DraftStatRow] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        name = str(section.get("sectionName") or section.get("label") or "unknown")
        for row in section.get("players") or []:
            if not isinstance(row, dict):
                continue
            player_id = _int(row.get("playerId")) or _int((row.get("player") or {}).get("id"))
            boost = _float(row.get("multiplierBonus"))
            if player_id is None or boost is None:
                continue
            player = row.get("player") or {}
            first, last = player.get("firstName"), player.get("lastName")
            out.append(
                DraftStatRow(
                    contest_id=contest_id,
                    player_id=player_id,
                    section=name,
                    card_boost=boost,
                    value=_float(row.get("value")),
                    draft_count=_int(row.get("count")),
                    avg_effective_multiplier=_float(row.get("avgMultiplier")),
                    avg_slot_position=_float(row.get("avgPosition")),
                    avg_score=_float(row.get("avgScore")),
                    highest_score=_float(row.get("highestScore")),
                    base_boosted_value=_float(row.get("baseBoostedValue")),
                    most_common_slot=row.get("mostCommonPosition"),
                    count_at_highest_slot=_int(row.get("countAtHighestPosition")),
                    slot_of_highest_score=row.get("positionOfHighestScore"),
                    team_id=_int(row.get("teamId")) or _int((row.get("team") or {}).get("id")),
                    display_name=f"{first} {last}" if first and last else None,
                )
            )
    return out


@dataclass(frozen=True)
class ParsedContest:
    """Everything Corpus C knows about one contest, after validation."""

    contest: ContestRecord
    entries: tuple[EntryRecord, ...]
    draft_stats: tuple[DraftStatRow, ...]
    missing_routes: tuple[str, ...]
    law_verified: bool
    law_error: str | None = None

    @property
    def has_field_evidence(self) -> bool:
        return bool(self.entries) and self.contest.is_finalized

    def boost_table(self) -> dict[int, float]:
        """Every player id whose card boost this contest reveals."""
        table: dict[int, float] = {}
        for row in self.draft_stats:
            table[row.player_id] = row.card_boost
        for entry in self.entries:
            for pick in entry.picks:
                table.setdefault(pick.player_id, pick.card_boost)
        return table

    def observed_values(self) -> dict[int, float]:
        """Finalized Real value per player, as the contest itself reported it."""
        values: dict[int, float] = {}
        for row in self.draft_stats:
            if row.value is not None:
                values[row.player_id] = row.value
        for entry in self.entries:
            for pick in entry.picks:
                if pick.value is not None:
                    values.setdefault(pick.player_id, pick.value)
        return values

    def real_ranks(self) -> dict[int, int]:
        """Finalized Real value rank per player, where an entry exposed it."""
        ranks: dict[int, int] = {}
        for entry in self.entries:
            for pick in entry.picks:
                if pick.real_rank is not None:
                    ranks.setdefault(pick.player_id, pick.real_rank)
        return ranks


def verify_scoring_law(entries: Sequence[EntryRecord]) -> tuple[bool, str | None]:
    """Check the leaderboard score equals the sum of the cards, per entry."""
    for entry in entries:
        total = entry.total_from_picks()
        if total is None or entry.score is None:
            continue
        if abs(total - entry.score) > 0.02:
            return False, f"entry_{entry.entry_id}_total_mismatch"
    return True, None


def load_contest(store: ContestStore, contest_id: int) -> ParsedContest | None:
    """Read one saved contest from disk and validate it end to end."""
    meta = store.read_route(contest_id, "meta")
    if meta is None:
        return None
    draftinfo = store.read_route(contest_id, "draftinfo")
    payoutinfo = store.read_route(contest_id, "payoutinfo")
    provenance_path = store.contest_dir(contest_id) / "meta.json.provenance.json"
    captured_at = datetime.now(UTC)
    if provenance_path.exists():
        stamped = _dt(json.loads(provenance_path.read_text())["captured_at"])
        if stamped is not None:
            captured_at = stamped
    contest = parse_contest_record(
        meta, draftinfo=draftinfo, payoutinfo=payoutinfo, captured_at=captured_at
    )
    missing: list[str] = []
    entries: list[EntryRecord] = []
    raw_entries = store.read_route(contest_id, "entries")
    if raw_entries is None:
        missing.append("entries")
    else:
        entries = parse_entries(
            raw_entries, contest_id=contest_id, slot_multipliers=contest.slot_multipliers
        )
    draft_stats: list[DraftStatRow] = []
    raw_stats = store.read_route(contest_id, "stats")
    if raw_stats is None:
        missing.append("stats")
    else:
        draft_stats = parse_draft_stats(raw_stats, contest_id=contest_id)
    if draftinfo is None:
        missing.append("draftinfo")
    if payoutinfo is None:
        missing.append("payoutinfo")
    verified, error = verify_scoring_law(entries)
    return ParsedContest(
        contest=contest,
        entries=tuple(entries),
        draft_stats=tuple(draft_stats),
        missing_routes=tuple(missing),
        law_verified=verified,
        law_error=error,
    )


def iter_contests(store: ContestStore, *, finalized_only: bool = False) -> Iterator[ParsedContest]:
    """Yield every parseable saved contest in ascending id order."""
    for contest_id in store.collected_ids():
        try:
            parsed = load_contest(store, contest_id)
        except (ContestParseError, ValueError):
            continue
        if parsed is None:
            continue
        if finalized_only and not parsed.contest.is_finalized:
            continue
        yield parsed
