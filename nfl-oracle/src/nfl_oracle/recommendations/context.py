"""Time-filtered NFL role, matchup and environment features.

Current statuses and forecasts are never used for historical training. Prior-game
statistics downloaded later may be used for explicitly retrospective evaluation,
but this is not proof of point-in-time historical source availability.
"""

from __future__ import annotations

import math
import re
import unicodedata
from bisect import bisect_right
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from statistics import fmean
from typing import Any
from zoneinfo import ZoneInfo

from nfl_oracle.recommendations.schema import EvidenceClock, Record, Slate, utc
from nfl_oracle.recommendations.sources import ContextSnapshot, Row, forecast_features

STAT_FIELDS = (
    "attempts",
    "passing_yards",
    "carries",
    "rushing_yards",
    "targets",
    "receptions",
    "receiving_yards",
    "target_share",
    "air_yards_share",
    "passing_epa",
    "rushing_epa",
    "receiving_epa",
    "def_tackles_solo",
    "def_sacks",
    "def_interceptions",
    "fg_att",
    "fg_made",
    "pat_att",
    "pat_made",
)

POSITION_FAMILIES: dict[str, frozenset[str]] = {
    "DB": frozenset({"DB", "CB", "FS", "SS", "S", "SAFETY"}),
    "DL": frozenset({"DL", "DE", "DT", "NT", "LDE", "RDE", "EDGE"}),
    "LB": frozenset({"LB", "ILB", "MLB", "OLB", "LOLB", "ROLB"}),
    "OL": frozenset({"OL", "OT", "T", "OG", "G", "C", "LT", "RT", "LG", "RG"}),
}


def normalize_team(value: str) -> str:
    name = value.upper().strip()
    return {"JAC": "JAX", "LA": "LAR", "WSH": "WAS"}.get(name, name)


def name_key(value: str) -> str:
    # Punctuation and accents are formatting. Suffixes and initials carry
    # identity and are deliberately retained; ambiguous names never auto-merge.
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _position_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def positions_compatible(requested: str, observed: str) -> bool:
    requested_key = _position_key(requested)
    observed_key = _position_key(observed)
    if requested_key == observed_key:
        return True
    requested_family = POSITION_FAMILIES.get(requested_key, frozenset({requested_key}))
    observed_family = POSITION_FAMILIES.get(observed_key, frozenset({observed_key}))
    return bool(requested_family & observed_family)


class RosterIdentityIndex:
    """Exact effective-week roster keys indexed once per snapshot."""

    def __init__(self, rosters: Iterable[Row]) -> None:
        self._rows: dict[tuple[int, int, str, str], list[tuple[str, str]]] = {}
        self._all_rows: list[tuple[int, int, str, str, str, str]] = []
        for row in rosters:
            season = _integer(row.get("season"))
            week = _integer(row.get("week"))
            stable_id = row.get("gsis_id")
            if season is None or week is None or not stable_id:
                continue
            key = (
                season,
                week,
                normalize_team(str(row.get("team"))),
                name_key(str(row.get("full_name", ""))),
            )
            self._rows.setdefault(key, []).append((str(row.get("position", "")), str(stable_id)))
            self._all_rows.append(
                (
                    season,
                    week,
                    normalize_team(str(row.get("team"))),
                    name_key(str(row.get("full_name", ""))),
                    str(row.get("position", "")),
                    str(stable_id),
                )
            )

    def resolve(self, name: str, team: str, position: str, season: int, week: int) -> str:
        key = (season, week, normalize_team(team), name_key(name))
        matches = {
            stable_id
            for observed_position, stable_id in self._rows.get(key, [])
            if positions_compatible(position, observed_position)
        }
        if len(matches) == 1:
            return next(iter(matches))
        if len(matches) > 1:
            raise ValueError("identity_ambiguous")

        # The Real feed carries generational suffixes and can retain a player's
        # old position or a stale team during the week-1 roster transition.
        # Relax one dimension at a time, but only accept a single stable ID.
        same_week = {
            stable_id
            for (
                observed_season,
                observed_week,
                _,
                observed_name,
                observed_position,
                stable_id,
            ) in self._all_rows
            if observed_season == season
            and observed_week == week
            and observed_name == key[3]
            and positions_compatible(position, observed_position)
        }
        if len(same_week) == 1:
            return next(iter(same_week))
        if len(same_week) > 1:
            raise ValueError("identity_ambiguous")

        def without_suffix(value: str) -> str:
            return re.sub(r"(?:jr|sr|ii|iii|iv|v)$", "", value)

        base_name = without_suffix(key[3])
        suffix_matches = {
            stable_id
            for _, _, _, observed_name, observed_position, stable_id in self._all_rows
            if without_suffix(observed_name) == base_name
            and positions_compatible(position, observed_position)
        }
        if len(suffix_matches) == 1:
            return next(iter(suffix_matches))
        if len(suffix_matches) > 1:
            raise ValueError("identity_ambiguous")
        raise ValueError("identity_unmatched")


def resolve_identity(
    name: str, team: str, position: str, season: int, week: int, rosters: tuple[Row, ...]
) -> str:
    return RosterIdentityIndex(rosters).resolve(name, team, position, season, week)


def crosswalk_external_ids(
    players: Iterable[tuple[int, str, str, str]],
    *,
    season: int,
    week: int,
    rosters: tuple[Row, ...],
) -> dict[int, str]:
    """Resolve Real player IDs to nflverse GSIS IDs for one effective week.

    The Real ID is retained as the dictionary key. Resolution intentionally
    uses exact normalized name, team, position, season, and week. A repeated
    name with different stable IDs is an error, rather than a best guess.
    """
    index = RosterIdentityIndex(rosters)
    result: dict[int, str] = {}
    for player_id, name, team, position in players:
        if player_id in result:
            raise ValueError("duplicate_external_player_id")
        result[player_id] = index.resolve(name, team, position, season, week)
    return result


def schedule_kickoff(row: Row) -> datetime:
    # nflverse gametime is US Eastern local time, including DST.
    return utc(
        datetime.fromisoformat(f"{row['gameday']}T{row['gametime']}").replace(
            tzinfo=ZoneInfo("America/New_York")
        )
    )


class ContextBundle(Record):
    features_by_player: dict[int, dict[str, float]]
    clocks_by_player: dict[int, EvidenceClock]
    external_ids: dict[int, str]
    missing_by_player: dict[int, tuple[str, ...]]
    source_status: dict[str, str]
    source_hashes: tuple[str, ...]
    evidence_mode: str = "captured_before_decision"


class HistoricalContextRow(Record):
    """Retrospective context joined to one finalized Corpus G observation."""

    player_id: int
    game_id: int
    external_id: str
    features: dict[str, float]
    clock: EvidenceClock
    source_hashes: tuple[str, ...]
    evidence_mode: str = "retrospective_reconstructed"


class HistoricalEnrichment(Record):
    """Time-safe retrospective joins, with exclusions kept explicit."""

    rows: tuple[HistoricalContextRow, ...]
    excluded: dict[str, int]
    source_hashes: tuple[str, ...]
    evidence_mode: str = "retrospective_reconstructed"


class HistoricalContext:
    """Index public weekly rows once. Current-game rows cannot enter priors.

    Only games at least 24 hours before the decision and before the target game
    enter aggregates. This conservative event buffer is not a publication clock.
    The caller still must enforce snapshot clocks for live use and label revised
    historical downloads as retrospective when evaluating historical decisions.
    """

    def __init__(self, snapshot: ContextSnapshot) -> None:
        schedules = snapshot.sources.get("schedules")
        self.schedule = {str(r["game_id"]): r for r in schedules.rows} if schedules else {}
        self.players: dict[str, list[Row]] = {}
        self.teams: dict[str, list[Row]] = {}
        self.allowed: dict[str, list[Row]] = {}
        self.roster_index = RosterIdentityIndex(
            snapshot.sources["rosters"].rows if snapshot.sources.get("rosters") is not None else ()
        )
        self.depth_index: dict[tuple[str, str], list[tuple[datetime, float]]] = {}
        source = snapshot.sources.get("player_stats")
        for row in source.rows if source else ():
            self.players.setdefault(str(row.get("player_id")), []).append(row)
        source = snapshot.sources.get("team_stats")
        for row in source.rows if source else ():
            self.teams.setdefault(normalize_team(str(row.get("team"))), []).append(row)
            self.allowed.setdefault(normalize_team(str(row.get("opponent_team"))), []).append(row)
        source = snapshot.sources.get("depth_charts")
        for row in source.rows if source else ():
            rank = _number(row.get("pos_rank"))
            if rank is None:
                continue
            try:
                observed = utc(datetime.fromisoformat(str(row["dt"])))
            except (KeyError, TypeError, ValueError):
                continue
            key = (str(row.get("gsis_id")), normalize_team(str(row.get("team"))))
            self.depth_index.setdefault(key, []).append((observed, rank))
        for values in self.depth_index.values():
            values.sort(key=lambda item: item[0])

    def resolve_identity(self, name: str, team: str, position: str, season: int, week: int) -> str:
        return self.roster_index.resolve(name, team, position, season, week)

    def latest_depth(self, gsis_id: str, team: str, before: datetime) -> tuple[float | None, bool]:
        values = self.depth_index.get((gsis_id, normalize_team(team)), [])
        if not values:
            return None, False
        times = [observed for observed, _ in values]
        index = bisect_right(times, utc(before))
        if index == 0:
            return None, False
        latest = times[index - 1]
        ranks = {rank for observed, rank in values[:index] if observed == latest}
        return (next(iter(ranks)), False) if len(ranks) == 1 else (None, True)

    def prior_rows(
        self,
        rows: list[Row],
        before: datetime,
        *,
        until: datetime | None = None,
        limit: int = 16,
    ) -> list[Row]:
        cutoff = min(utc(before), utc(until)) if until is not None else utc(before)
        eligible: dict[str, tuple[datetime, Row]] = {}
        for row in rows:
            game_id = str(row.get("game_id", ""))
            game = self.schedule.get(game_id)
            if game is None:
                continue
            try:
                kickoff = schedule_kickoff(game)
            except (KeyError, TypeError, ValueError):
                continue
            if kickoff >= cutoff or kickoff + timedelta(hours=24) >= utc(before):
                continue
            if game_id in eligible and eligible[game_id][1] != row:
                raise ValueError("conflicting_weekly_stats")
            eligible[game_id] = (kickoff, row)
        return [r for _, r in sorted(eligible.values(), key=lambda item: item[0])[-limit:]]

    def features(
        self,
        gsis_id: str | None,
        team: str,
        opponent: str,
        before: datetime,
        kickoff: datetime,
        *,
        season: int | None = None,
    ) -> dict[str, float]:
        rows = self.prior_rows(self.players.get(gsis_id or "", []), before, until=kickoff)
        result = {"history_game_count": float(len(rows))}
        for field in STAT_FIELDS:
            values = [_number(r.get(field)) for r in rows]
            finite = [v for v in values if v is not None]
            if finite:
                result[f"prior_{field}"] = fmean(finite)
        for field, identity in (("team_pace_prior", team), ("opponent_pace_prior", opponent)):
            priors = self.prior_rows(
                self.teams.get(normalize_team(identity), []), before, until=kickoff
            )
            plays = []
            for row in priors:
                counts = [_number(row.get(k)) for k in ("attempts", "carries", "sacks_suffered")]
                if all(v is not None for v in counts):
                    plays.append(sum(v for v in counts if v is not None))
            if plays:
                result[field] = fmean(plays)
        allowed = self.prior_rows(
            self.allowed.get(normalize_team(opponent), []), before, until=kickoff
        )
        for field in ("passing_yards", "rushing_yards"):
            values = [_number(r.get(field)) for r in allowed]
            finite = [v for v in values if v is not None]
            if finite:
                result[f"opponent_{field}_allowed_prior"] = fmean(finite)
        prior_games = []
        for game in self.schedule.values():
            game_season = _integer(game.get("season"))
            if game_season is None:
                continue
            if season is not None and game_season != season:
                continue
            if normalize_team(team) not in (
                normalize_team(str(game.get("home_team"))),
                normalize_team(str(game.get("away_team"))),
            ):
                continue
            try:
                prior = schedule_kickoff(game)
            except (ValueError, KeyError, TypeError):
                continue
            if prior < utc(kickoff) and prior + timedelta(hours=24) < utc(before):
                prior_games.append(prior)
        if prior_games:
            result["days_rest"] = (utc(kickoff).date() - max(prior_games).date()).days
        return result


def enrich_historical_rows(
    rows: Iterable[Any],
    snapshot: ContextSnapshot,
    *,
    metadata: Mapping[tuple[int, int], Mapping[str, Any]],
) -> HistoricalEnrichment:
    """Join finalized Corpus G rows to retrospective nflverse context.

    ``metadata`` is keyed by ``(Real player_id, Real game_id)`` and must carry
    ``name``, ``team``, ``opponent``, ``position``, ``season``, and ``week``.
    The caller obtains those values from the immutable Corpus G feed, so this
    helper never guesses a team from a current roster or a player name alone.

    nflreadpy releases are captured snapshots, not point-in-time archives. The
    returned clock therefore retains the snapshot's actual capture time, even
    when it is after the target kickoff. Consumers may use these rows for
    retrospective reconstruction only and must not relabel the clock as live
    evidence.
    """
    history = HistoricalContext(snapshot)
    hashes = tuple(source.sha256 for source in snapshot.sources.values())
    captured = max(
        (source.clock.captured_at for source in snapshot.sources.values()),
        default=datetime.min.replace(tzinfo=UTC),
    )
    available = max(
        (source.clock.source_available_at for source in snapshot.sources.values()),
        default=captured,
    )
    enriched: list[HistoricalContextRow] = []
    excluded: dict[str, int] = {}
    roster = snapshot.sources.get("rosters")
    depth = snapshot.sources.get("depth_charts")
    for row in rows:
        try:
            player_id = int(row.player_id)
            game_id = int(row.game_id)
            event = metadata[(player_id, game_id)]
            name = str(event["name"])
            team = str(event["team"])
            opponent = str(event["opponent"])
            position = str(event["position"])
            season = int(event["season"])
            week = int(event["week"])
            kickoff = utc(row.kickoff_at)
            if roster is None:
                raise ValueError("roster_missing")
            external_id = history.resolve_identity(name, team, position, season, week)
            values = history.features(
                external_id,
                team,
                opponent,
                kickoff,
                kickoff,
                season=season,
            )
            if depth is not None:
                depth_rank, depth_conflict = history.latest_depth(external_id, team, kickoff)
                if depth_rank is not None:
                    values["depth_rank"] = depth_rank
                    values["depth_first_team"] = float(depth_rank == 1)
                elif depth_conflict:
                    excluded["depth_rank_conflicting_packages"] = (
                        excluded.get("depth_rank_conflicting_packages", 0) + 1
                    )
            enriched.append(
                HistoricalContextRow(
                    player_id=player_id,
                    game_id=game_id,
                    external_id=external_id,
                    features=values,
                    clock=EvidenceClock(
                        source_available_at=available,
                        captured_at=captured,
                    ),
                    source_hashes=hashes,
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            code = str(error) if str(error) else type(error).__name__
            excluded[code] = excluded.get(code, 0) + 1
    return HistoricalEnrichment(rows=tuple(enriched), excluded=excluded, source_hashes=hashes)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _injury_category(value: str | None) -> str:
    """Keep provider availability categories categorical and probability-free."""
    normalized = re.sub(r"[^a-z]", "", (value or "").lower())
    aliases = {
        "q": "questionable",
        "questionable": "questionable",
        "d": "doubtful",
        "doubtful": "doubtful",
        "o": "out",
        "out": "out",
        "active": "active",
        "available": "active",
        "inactive": "inactive",
        "ir": "ir",
        "injuredreserve": "ir",
        "suspended": "suspended",
        "limited": "limited",
        "dnp": "dnp",
        "didnotparticipate": "dnp",
        "full": "full",
        "fullparticipation": "full",
    }
    return aliases.get(normalized, "unknown")


def build_context(slate: Slate, snapshot: ContextSnapshot, decision_at: datetime) -> ContextBundle:
    now = utc(decision_at)
    # Reject future captures as a group. Historical use must call the explicit
    # historical-only helper, which never sees live status, depth or forecasts.
    for source in snapshot.sources.values():
        source.clock.assert_available(now)
    history = HistoricalContext(snapshot)
    games = {g.game_id: g for g in slate.games}
    features: dict[int, dict[str, float]] = {}
    clocks: dict[int, EvidenceClock] = {}
    identities: dict[int, str] = {}
    missing: dict[int, tuple[str, ...]] = {}
    roster = snapshot.sources.get("rosters")
    depth = snapshot.sources.get("depth_charts")
    for player in slate.candidates:
        player.clock.assert_available(now)
        game = games[player.game_id]
        schedule_matches = [
            r
            for r in history.schedule.values()
            if _integer(r.get("season")) == game.season
            and r.get("gameday")
            == game.kickoff_at.astimezone(ZoneInfo("America/New_York")).date().isoformat()
            and normalize_team(str(r.get("home_team"))) == normalize_team(game.home_team)
            and normalize_team(str(r.get("away_team"))) == normalize_team(game.away_team)
        ]
        gaps: list[str] = []
        gsis_id = None
        scheduled = schedule_matches[0] if len(schedule_matches) == 1 else None
        if scheduled is None:
            gaps.append("schedule_identity_unmatched")
        elif roster is None or (now - roster.clock.captured_at).total_seconds() > 24 * 3600:
            gaps.append("roster_missing_or_stale")
        else:
            try:
                gsis_id = history.resolve_identity(
                    player.name,
                    player.team,
                    player.position,
                    game.season,
                    int(scheduled["week"]),
                )
                identities[player.player_id] = gsis_id
            except ValueError as error:
                gaps.append(str(error))
        vector = history.features(
            gsis_id,
            player.team,
            player.opponent,
            now,
            game.kickoff_at,
            season=game.season,
        )
        vector["is_home"] = float(player.team_id == game.home_team_id)
        status = _injury_category(player.injury_status)
        for category in (
            "active",
            "questionable",
            "doubtful",
            "out",
            "inactive",
            "ir",
            "suspended",
            "limited",
            "dnp",
            "full",
            "unknown",
        ):
            vector[f"injury_{category}"] = float(status == category)
        if status == "unknown":
            gaps.append("injury_status_unknown")
        if depth and gsis_id:
            depth_rank, depth_conflict = history.latest_depth(gsis_id, player.team, now)
            if depth_rank is not None:
                vector["depth_rank"] = depth_rank
                vector["depth_first_team"] = float(depth_rank == 1)
            elif depth_conflict:
                gaps.append("depth_rank_conflicting_packages")
        if "depth_rank" not in vector:
            gaps.append("depth_rank_missing")
        weather = (
            snapshot.sources.get(f"weather:{scheduled.get('stadium_id')}") if scheduled else None
        )
        if weather:
            vector.update(forecast_features(weather, game.kickoff_at, now))
        if "weather_temp_f" not in vector:
            gaps.append(
                "weather_indoor" if weather and weather.status == "indoor" else "weather_missing"
            )
        if not vector["history_game_count"]:
            gaps.append("player_history_missing")
        features[player.player_id] = vector
        captured = max(
            [player.clock.captured_at] + [s.clock.captured_at for s in snapshot.sources.values()]
        )
        available = max(
            [player.clock.source_available_at]
            + [s.clock.source_available_at for s in snapshot.sources.values()]
        )
        clocks[player.player_id] = EvidenceClock(
            captured_at=captured, source_available_at=available
        )
        missing[player.player_id] = tuple(gaps)
    return ContextBundle(
        features_by_player=features,
        clocks_by_player=clocks,
        external_ids=identities,
        missing_by_player=missing,
        source_status={k: v.status for k, v in snapshot.sources.items()},
        source_hashes=tuple(s.sha256 for s in snapshot.sources.values()),
    )
