"""Infer NhlContestContract fields from Real Sports payloads.

Only resolves a field when the payload evidence is explicit. Unknowns stay
unknown (or None) rather than being guessed from NFL/WNBA defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nhl_oracle.contract.schema import (
    BoostRegime,
    ContestFormat,
    LockScope,
    NhlCandidate,
    NhlContestContract,
)

GOALIE_POSITION_TOKENS = frozenset({"G", "GOALIE", "GOALTENDER"})


@dataclass(frozen=True)
class DiscoveryEvidence:
    """Machine-readable notes for STATUS.md / audit records."""

    notes: tuple[str, ...]
    contest_ids: tuple[int, ...]
    game_ids: tuple[int, ...]
    players_seen: int
    players_resolved: int
    games_scheduled: int
    games_captured: int


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def extract_slot_multipliers(draftinfo: dict[str, Any]) -> tuple[float, ...] | None:
    info = _as_dict(draftinfo.get("info"))
    raw = info.get("defaultMultipliers")
    if not isinstance(raw, list) or not raw:
        return None
    try:
        values = tuple(float(x) for x in raw)
    except (TypeError, ValueError):
        return None
    if any(v <= 0 for v in values):
        return None
    return values


def extract_lineup_size(meta: dict[str, Any], draftinfo: dict[str, Any]) -> int | None:
    contest = _as_dict(_as_dict(meta.get("info")).get("contest"))
    additional = _as_dict(contest.get("additionalInfo"))
    for raw in (additional.get("lineupSize"), _as_dict(draftinfo.get("info")).get("lineupSize")):
        if isinstance(raw, int) and raw > 0:
            return raw
        if isinstance(raw, str) and raw.isdigit() and int(raw) > 0:
            return int(raw)
    return None


def extract_score_value_label(
    draftinfo: dict[str, Any],
    players_payloads: list[dict[str, Any]],
    contest_stats: dict[str, Any] | None = None,
) -> str | None:
    info = _as_dict(draftinfo.get("info"))
    for key in ("scoreValueLabel", "valueLabel", "ratingLabel"):
        raw = info.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    if contest_stats is not None:
        for section in _as_list(contest_stats.get("draftStats")):
            for row in _as_list(_as_dict(section).get("players")):
                if isinstance(row, dict) and row.get("value") is not None:
                    return "value"
    for payload in players_payloads:
        for player in _as_list(payload.get("players")):
            if not isinstance(player, dict):
                continue
            for key in ("fantasyPoints", "value", "rating", "scoreValue"):
                if key in player and player[key] is not None:
                    return key
    return None


def goalie_eligible_from_players(players_payloads: list[dict[str, Any]]) -> bool | None:
    saw_any_position = False
    for payload in players_payloads:
        for player in _as_list(payload.get("players")):
            if not isinstance(player, dict):
                continue
            position = str(player.get("position") or player.get("pos") or "").strip().upper()
            if not position:
                continue
            saw_any_position = True
            token = position.split("-", 1)[0].split("/", 1)[0].strip()
            if token in GOALIE_POSITION_TOKENS or position in GOALIE_POSITION_TOKENS:
                return True
    if not saw_any_position:
        return None
    return False


def _collect_player_card_bonuses(
    players_payloads: list[dict[str, Any]],
) -> tuple[list[float], int]:
    """Return (bonus values found, count of player rows inspected)."""

    bonuses: list[float] = []
    players_seen = 0
    for payload in players_payloads:
        for player in _as_list(payload.get("players")):
            if not isinstance(player, dict):
                continue
            players_seen += 1
            raw = player.get("multiplierBonus")
            if raw is None:
                raw = player.get("cardBoost")
            if raw is None:
                continue
            try:
                bonuses.append(float(raw))
            except (TypeError, ValueError):
                continue
    return bonuses, players_seen


def _collect_contest_stats_bonuses(
    contest_stats: dict[str, Any] | None,
) -> list[float]:
    bonuses: list[float] = []
    if contest_stats is None:
        return bonuses
    for section in _as_list(contest_stats.get("draftStats")):
        for row in _as_list(_as_dict(section).get("players")):
            if not isinstance(row, dict):
                continue
            raw = row.get("multiplierBonus")
            if raw is None:
                continue
            try:
                bonuses.append(float(raw))
            except (TypeError, ValueError):
                continue
    return bonuses


def _regime_from_bonuses(bonuses: list[float]) -> BoostRegime:
    if not bonuses:
        return BoostRegime.UNKNOWN
    if any(b != 0 for b in bonuses):
        return BoostRegime.FLAT
    return BoostRegime.NONE


def boost_regime_from_players_and_stats(
    players_payloads: list[dict[str, Any]],
    contest_stats: dict[str, Any] | None = None,
) -> tuple[BoostRegime, tuple[str, ...]]:
    """Infer live boost regime, preferring current-slate player cards.

    Pre-boost / zero-boost rule: until every NHL team has played, live cards
    carry no card boosts. Historical contest draftStats may still show nonzero
    ``multiplierBonus`` from a later window; that must not override live-slate
    absence or zeros. Returns (regime, notes).
    """

    notes: list[str] = []
    card_bonuses, players_seen = _collect_player_card_bonuses(players_payloads)
    stats_bonuses = _collect_contest_stats_bonuses(contest_stats)
    card_regime = _regime_from_bonuses(card_bonuses)
    stats_regime = _regime_from_bonuses(stats_bonuses)

    if players_seen > 0 and not card_bonuses:
        # Live game cards inspected and none expose a boost field: pre-boost.
        regime = BoostRegime.NONE
        notes.append(
            "boost_regime=none from current-slate player cards "
            f"(inspected={players_seen}, no multiplierBonus/cardBoost fields; pre-boost)"
        )
        if stats_regime is BoostRegime.FLAT:
            notes.append(
                "historical_contest_draftStats_had_nonzero_multiplierBonus "
                "(not applied to live pre-boost regime)"
            )
        return regime, tuple(notes)

    if card_regime is BoostRegime.NONE:
        notes.append("boost_regime=none (multiplierBonus present on player cards and all zero)")
        if stats_regime is BoostRegime.FLAT:
            notes.append(
                "historical_contest_draftStats_had_nonzero_multiplierBonus "
                "(not applied; live cards are zero)"
            )
        return BoostRegime.NONE, tuple(notes)

    if card_regime is BoostRegime.FLAT:
        notes.append(
            "boost_regime=flat from nonzero multiplierBonus/cardBoost on live player cards"
        )
        return BoostRegime.FLAT, tuple(notes)

    # No usable live player rows: fall back to contest draftStats only.
    if stats_regime is BoostRegime.FLAT:
        notes.append(
            "boost_regime=flat from contest draftStats multiplierBonus "
            "(no live player-card boost fields available)"
        )
        return BoostRegime.FLAT, tuple(notes)
    if stats_regime is BoostRegime.NONE:
        notes.append(
            "boost_regime=none (contest draftStats multiplierBonus present and all zero; "
            "no live player-card boost fields)"
        )
        return BoostRegime.NONE, tuple(notes)

    notes.append(
        "boost_regime still unknown (no multiplierBonus/cardBoost on players or draftStats)"
    )
    return BoostRegime.UNKNOWN, tuple(notes)


def lock_scope_from_meta(meta: dict[str, Any]) -> LockScope:
    info = _as_dict(meta.get("info"))
    if isinstance(info.get("isLocked"), bool) or isinstance(
        _as_dict(info.get("contest")).get("isLocked"), bool
    ):
        return LockScope.PER_CONTEST
    return LockScope.UNKNOWN


def format_from_lineup(
    lineup_size: int | None, multipliers: tuple[float, ...] | None
) -> ContestFormat:
    if lineup_size == 5 and multipliers is not None and len(multipliers) == 5:
        return ContestFormat.FIVE_CARD_ORDERED
    if lineup_size is not None and lineup_size > 5:
        return ContestFormat.ROSTER_CONSTRUCTION
    return ContestFormat.UNKNOWN


def _score_map_from_contest_stats(
    contest_stats: dict[str, Any] | None,
) -> dict[int, float]:
    scores: dict[int, float] = {}
    if contest_stats is None:
        return scores
    for section in _as_list(contest_stats.get("draftStats")):
        for row in _as_list(_as_dict(section).get("players")):
            if not isinstance(row, dict):
                continue
            pid = row.get("playerId")
            if not isinstance(pid, int) or pid <= 0:
                nested = _as_dict(row.get("player"))
                nested_id = nested.get("id")
                pid = nested_id if isinstance(nested_id, int) else None
            if not isinstance(pid, int) or pid <= 0:
                continue
            raw = row.get("value")
            if raw is None:
                continue
            try:
                scores[pid] = float(raw)
            except (TypeError, ValueError):
                continue
    return scores


def _position_map_from_players(
    players_payloads: list[dict[str, Any]],
) -> dict[int, str]:
    positions: dict[int, str] = {}
    for payload in players_payloads:
        for player in _as_list(payload.get("players")):
            if not isinstance(player, dict):
                continue
            pid = player.get("id")
            if not isinstance(pid, int) or pid <= 0:
                continue
            position = str(player.get("position") or player.get("pos") or "").strip()
            if position:
                positions[pid] = position
    return positions


def candidates_from_players(
    players_payloads: list[dict[str, Any]],
    *,
    captured_at: str,
    contest_stats: dict[str, Any] | None = None,
) -> tuple[NhlCandidate, ...]:
    """Build audit candidates, preferring contest draftStats values for scores.

    Live game player cards often omit the contest score/value field; historical
    and live contest `/stats` draftStats carry the authoritative `value`.
    """

    score_map = _score_map_from_contest_stats(contest_stats)
    position_map = _position_map_from_players(players_payloads)
    out: list[NhlCandidate] = []
    seen: set[int] = set()

    # Prefer scored contest-pool rows when present so pool_completeness can pass
    # on real redacted fixtures.
    if score_map:
        for pid, score in score_map.items():
            if pid in seen:
                continue
            seen.add(pid)
            out.append(
                NhlCandidate(
                    player_id=pid,
                    position=position_map.get(pid, "UNK"),
                    score_value=score,
                    captured_at=captured_at,
                    identity_resolved=True,
                    identity_ambiguous=False,
                )
            )
        return tuple(out)

    for payload in players_payloads:
        for player in _as_list(payload.get("players")):
            if not isinstance(player, dict):
                continue
            player_id = player.get("id")
            if not isinstance(player_id, int) or player_id <= 0 or player_id in seen:
                continue
            seen.add(player_id)
            position = str(player.get("position") or player.get("pos") or "UNK")
            score_value: float | None = None
            for key in ("fantasyPoints", "value", "rating", "scoreValue"):
                raw = player.get(key)
                if raw is None:
                    continue
                try:
                    score_value = float(raw)
                    break
                except (TypeError, ValueError):
                    continue
            out.append(
                NhlCandidate(
                    player_id=player_id,
                    position=position,
                    score_value=score_value,
                    captured_at=captured_at,
                    identity_resolved=True,
                    identity_ambiguous=False,
                )
            )
    return tuple(out)


def discover_contract(
    *,
    meta: dict[str, Any],
    draftinfo: dict[str, Any],
    players_payloads: list[dict[str, Any]],
    contest_ids: tuple[int, ...],
    game_ids: tuple[int, ...],
    games_scheduled: int,
    games_captured: int,
    captured_at: str,
    contest_stats: dict[str, Any] | None = None,
) -> tuple[NhlContestContract, DiscoveryEvidence, tuple[NhlCandidate, ...]]:
    notes: list[str] = []
    multipliers = extract_slot_multipliers(draftinfo)
    lineup_size = extract_lineup_size(meta, draftinfo)
    fmt = format_from_lineup(lineup_size, multipliers)
    if fmt is ContestFormat.FIVE_CARD_ORDERED:
        notes.append(
            f"format=five_card_ordered from lineupSize={lineup_size} and "
            f"defaultMultipliers={multipliers}"
        )
    elif fmt is ContestFormat.UNKNOWN:
        notes.append(f"format still unknown (lineupSize={lineup_size}, multipliers={multipliers})")

    lock_scope = lock_scope_from_meta(meta)
    if lock_scope is LockScope.PER_CONTEST:
        notes.append("lock_scope=per_contest from contest-level isLocked on meta")
    else:
        notes.append("lock_scope still unknown (no contest-level isLocked boolean)")

    boost, boost_notes = boost_regime_from_players_and_stats(players_payloads, contest_stats)
    notes.extend(boost_notes)

    goalie = goalie_eligible_from_players(players_payloads)
    if goalie is True:
        notes.append("goalie_eligible=True (G/goalie position present in player pool)")
    elif goalie is False:
        notes.append("goalie_eligible=False (positions seen, no goalie token)")
    else:
        notes.append("goalie_eligible still unknown (no positions on player payloads)")

    label = extract_score_value_label(draftinfo, players_payloads, contest_stats)
    if label:
        notes.append(f"score_value_label={label}")
    else:
        notes.append("score_value_label still unknown")

    roster_size = lineup_size if isinstance(lineup_size, int) and lineup_size > 0 else 5
    slot_multipliers = (
        multipliers if multipliers is not None and len(multipliers) == roster_size else None
    )
    contract = NhlContestContract(
        format=fmt,
        lock_scope=lock_scope,
        boost_regime=boost,
        score_value_label=label,
        roster_size=roster_size,
        slot_multipliers=slot_multipliers,
        goalie_eligible=goalie,
    )
    candidates = candidates_from_players(
        players_payloads, captured_at=captured_at, contest_stats=contest_stats
    )
    evidence = DiscoveryEvidence(
        notes=tuple(notes),
        contest_ids=contest_ids,
        game_ids=game_ids,
        players_seen=len(candidates),
        players_resolved=sum(
            1 for c in candidates if c.identity_resolved and not c.identity_ambiguous
        ),
        games_scheduled=games_scheduled,
        games_captured=games_captured,
    )
    return contract, evidence, candidates
