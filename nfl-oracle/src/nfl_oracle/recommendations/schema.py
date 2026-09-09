"""Validated recommendation inputs. Research and submission gates remain separate."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Finite = Annotated[float, Field(allow_inf_nan=False)]
PositiveId = Annotated[int, Field(gt=0, strict=True)]


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone_required")
    return value.astimezone(UTC)


def fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceClock(Record):
    source_available_at: datetime
    captured_at: datetime

    _aware = field_validator("source_available_at", "captured_at")(utc)

    def assert_available(self, decision_at: datetime) -> None:
        if max(self.source_available_at, self.captured_at) > utc(decision_at):
            raise ValueError("future_evidence")


class Game(Record):
    game_id: PositiveId
    season: int
    kickoff_at: datetime
    home_team_id: PositiveId
    away_team_id: PositiveId
    home_team: str
    away_team: str
    status: str

    _aware = field_validator("kickoff_at")(utc)

    @model_validator(mode="after")
    def distinct_teams(self) -> Game:
        if self.home_team_id == self.away_team_id:
            raise ValueError("game_requires_distinct_teams")
        return self


class Contest(Record):
    contest_id: PositiveId
    contest_type: Literal["sport"] = "sport"
    sport: Literal["nfl"] = "nfl"
    day: date
    end_day: date
    lineup_size: Literal[5] = 5
    slot_multipliers: tuple[Finite, Finite, Finite, Finite, Finite]
    is_locked: bool
    is_finalized: bool
    clock: EvidenceClock
    # Provider lock is nullable. Operational cutoff is explicitly separate.
    provider_lock_at: datetime | None = None
    evidence_sha256: str
    contest_entry: Literal[False] = False

    @field_validator("provider_lock_at")
    @classmethod
    def lock_aware(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None

    @model_validator(mode="after")
    def valid_contract(self) -> Contest:
        if self.end_day < self.day or any(v <= 0 for v in self.slot_multipliers):
            raise ValueError("invalid_contest_contract")
        if self.slot_multipliers != (2.0, 1.8, 1.6, 1.4, 1.2):
            raise ValueError("unsupported_slot_contract")
        return self


class Candidate(Record):
    player_id: PositiveId
    game_id: PositiveId
    team_id: PositiveId
    name: str
    position: str
    team: str
    opponent: str
    injury_status: str | None
    card_boost: Annotated[Finite, Field(ge=0, le=3)]
    boost_source: Literal["prelock_rating_search"] = "prelock_rating_search"
    clock: EvidenceClock


class Slate(Record):
    contest: Contest
    games: tuple[Game, ...]
    candidates: tuple[Candidate, ...]
    captured_at: datetime
    source_hashes: tuple[str, ...]
    pool_roster_count: int
    pool_search_matched_count: int
    pool_unmatched_ids: tuple[int, ...] = ()
    pool_complete: bool
    # A search hit proves observed eligibility; an unmatched roster row is unknown.
    pool_method: Literal["roster_exact_id_search"] = "roster_exact_id_search"
    boost_regime: Literal["zero_boost", "provider_boosts_present"]
    boost_nonzero_count: int
    boost_max: Annotated[Finite, Field(ge=0, le=3)]

    _aware = field_validator("captured_at")(utc)

    @model_validator(mode="before")
    @classmethod
    def fill_operational_declarations(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        prepared = dict(data)
        candidates = prepared.get("candidates")
        if isinstance(candidates, tuple | list):
            boosts: list[float] = []
            for item in candidates:
                raw: Any
                if isinstance(item, Candidate):
                    raw = item.card_boost
                elif isinstance(item, Mapping):
                    raw = item.get("card_boost")
                else:
                    continue
                if isinstance(raw, bool) or raw is None:
                    continue
                boosts.append(float(raw))
            nonzero = sum(1 for value in boosts if value > 0)
            prepared.setdefault("boost_nonzero_count", nonzero)
            prepared.setdefault("boost_max", max(boosts) if boosts else 0.0)
            prepared.setdefault(
                "boost_regime", "zero_boost" if nonzero == 0 else "provider_boosts_present"
            )
            roster = prepared.get("pool_roster_count")
            matched = prepared.get("pool_search_matched_count")
            unmatched = prepared.get("pool_unmatched_ids") or ()
            if isinstance(roster, int) and isinstance(matched, int):
                prepared.setdefault(
                    "pool_complete",
                    roster == matched == len(candidates) and len(tuple(unmatched)) == 0,
                )
        return prepared

    @model_validator(mode="after")
    def valid_identity(self) -> Slate:
        games = {g.game_id: g for g in self.games}
        ids = {p.player_id for p in self.candidates}
        if not games or len(games) != len(self.games):
            raise ValueError("missing_or_duplicate_games")
        if len(ids) != len(self.candidates):
            raise ValueError("duplicate_player")
        if self.pool_roster_count < 0 or self.pool_search_matched_count < 0:
            raise ValueError("negative_pool_count")
        if self.pool_search_matched_count != len(self.candidates):
            raise ValueError("pool_match_count_mismatch")
        if self.pool_roster_count < self.pool_search_matched_count:
            raise ValueError("pool_roster_count_below_matches")
        expected_complete = (
            self.pool_roster_count == self.pool_search_matched_count and not self.pool_unmatched_ids
        )
        if self.pool_complete != expected_complete:
            raise ValueError("pool_complete_declaration_mismatch")
        boosts = [p.card_boost for p in self.candidates]
        nonzero = sum(1 for boost in boosts if boost > 0)
        if self.boost_nonzero_count != nonzero:
            raise ValueError("boost_count_declaration_mismatch")
        max_boost = max(boosts) if boosts else 0.0
        if abs(self.boost_max - max_boost) > 1e-9:
            raise ValueError("boost_max_declaration_mismatch")
        expected_regime = "zero_boost" if nonzero == 0 else "provider_boosts_present"
        if self.boost_regime != expected_regime:
            raise ValueError("boost_regime_declaration_mismatch")
        for player in self.candidates:
            game = games.get(player.game_id)
            if game is None or player.team_id not in (game.home_team_id, game.away_team_id):
                raise ValueError("player_game_identity_mismatch")
        return self

    def cutoff(self) -> datetime:
        earliest = min(g.kickoff_at for g in self.games)
        lock = self.contest.provider_lock_at
        return min(earliest, lock) if lock is not None else earliest

    def assert_prelock(self, decision_at: datetime, *, max_age_seconds: int = 900) -> None:
        now = utc(decision_at)
        if self.contest.is_locked or self.contest.is_finalized or now >= self.cutoff():
            raise ValueError("slate_locked")
        if any(g.status != "scheduled" for g in self.games):
            raise ValueError("game_not_scheduled")
        self.contest.clock.assert_available(now)
        if (
            self.captured_at > now
            or (now - self.contest.clock.captured_at).total_seconds() > max_age_seconds
        ):
            raise ValueError("stale_or_future_slate")
        for player in self.candidates:
            player.clock.assert_available(now)
            if (now - player.clock.captured_at).total_seconds() > max_age_seconds:
                raise ValueError("stale_player")
        if not self.pool_complete:
            raise ValueError("incomplete_player_pool")
        if len(self.candidates) < 5:
            raise ValueError("fewer_than_five_candidates")
