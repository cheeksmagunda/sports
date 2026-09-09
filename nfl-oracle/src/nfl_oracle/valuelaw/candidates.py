"""Live candidate pool for an NFL five-card slate, joined to Corpus G history.

Three capabilities, all read-only:

* :func:`load_slate` / :func:`load_candidates` read a saved slate artifact and
  return the eligible pool, optionally joined to prior box-score values.
* :func:`refresh_live_slate` re-collects the pool from the provider through the
  audited :class:`~nfl_oracle.recommendations.provider.NFLReader` and writes a
  timestamped artifact. It issues GETs only.
* :func:`build_history_index` / :func:`join_history` join Real player ids to
  Corpus G ``playerBoxScores[].value`` labels.

Nothing here enters a contest, and no submission path may be added.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
from oracle_core.artifacts import atomic_write_json

from nfl_oracle.common.paths import resolve_project_root
from nfl_oracle.recommendations.provider import NFLReader, ObservationStore
from nfl_oracle.recommendations.schema import Candidate, Record, Slate, utc

LIVE_CONTEST_ID = 2141
LIVE_DAY = date(2026, 9, 9)
LIVE_GAME_ID = 19457

_ARTIFACT_STEM = re.compile(r"^slate_(?P<contest>[1-9][0-9]*)(?P<suffix>_live_[0-9TZ]+|_fresh)?$")


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------


def project_root() -> Path:
    """Return the nfl-oracle application root."""

    return resolve_project_root(__file__)


def artifacts_dir(root: Path | None = None) -> Path:
    """Return the directory holding saved slate artifacts."""

    return (root or project_root()) / "data" / "artifacts"


def corpus_g_root(root: Path | None = None) -> Path:
    """Return the Corpus G raw directory (``<season>/<game_id>/stats.json``)."""

    return (root or project_root()) / "data" / "raw" / "corpus_g"


def observations_dir(root: Path | None = None) -> Path:
    """Return the content-addressed provider observation store directory."""

    return (root or project_root()) / "data" / "raw" / "observations"


def slate_artifact_paths(
    contest_id: int = LIVE_CONTEST_ID, *, root: Path | None = None
) -> tuple[Path, ...]:
    """Return every saved artifact for *contest_id*, oldest capture last.

    Ordering is newest first by modification time so callers can take index 0
    for the most recent capture without re-reading each file.
    """

    directory = artifacts_dir(root)
    if not directory.is_dir():
        return ()
    found: list[Path] = []
    for path in directory.glob(f"slate_{contest_id}*.json"):
        match = _ARTIFACT_STEM.match(path.stem)
        if match is not None and int(match.group("contest")) == contest_id:
            found.append(path)
    return tuple(sorted(found, key=lambda p: (p.stat().st_mtime, p.name), reverse=True))


def latest_slate_path(contest_id: int = LIVE_CONTEST_ID, *, root: Path | None = None) -> Path:
    """Return the most recently written saved artifact for *contest_id*."""

    paths = slate_artifact_paths(contest_id, root=root)
    if not paths:
        raise FileNotFoundError(f"no_slate_artifact_for_contest:{contest_id}")
    return paths[0]


# --------------------------------------------------------------------------
# Slate loading
# --------------------------------------------------------------------------


def load_slate(path: Path | str | None = None, *, contest_id: int = LIVE_CONTEST_ID) -> Slate:
    """Validate and return a saved slate artifact.

    Staleness and lock gating are deliberately not applied here. The artifact
    carries ``captured_at`` and the contest lock flags; the caller decides
    whether the capture is fresh enough for its own decision.
    """

    target = Path(path) if path is not None else latest_slate_path(contest_id)
    raw: Any = json.loads(target.read_text())
    if not isinstance(raw, dict):
        raise ValueError("slate_artifact_object_required")
    return Slate.model_validate(raw)


# --------------------------------------------------------------------------
# Corpus G history
# --------------------------------------------------------------------------


class HistoryGame(Record):
    """One prior finalized player-game observed in Corpus G."""

    season: int
    game_id: int
    played_at: datetime
    position: str
    team_id: int
    box_value: float
    fantasy_points_fanduel: float | None


class PlayerHistory(Record):
    """Aggregated Corpus G box-score history for one Real player id."""

    player_id: int
    games: int
    mean_box_value: float
    max_box_value: float
    min_box_value: float
    last_box_value: float
    last_played_at: datetime
    seasons: tuple[int, ...]
    values: tuple[float, ...]

    @property
    def recent_values(self) -> tuple[float, ...]:
        """Box values ordered oldest to newest, same order as :attr:`values`."""

        return self.values


class CandidateRow(Record):
    """A live candidate paired with whatever prior history its id has."""

    candidate: Candidate
    history: PlayerHistory | None

    @property
    def player_id(self) -> int:
        return self.candidate.player_id

    @property
    def has_history(self) -> bool:
        return self.history is not None


def iter_corpus_g_stats(root: Path | None = None) -> Iterator[tuple[int, int, Path]]:
    """Yield ``(season, game_id, stats_path)`` for every Corpus G game."""

    base = corpus_g_root(root)
    if not base.is_dir():
        return
    for season_dir in sorted(base.iterdir()):
        if not season_dir.is_dir() or not season_dir.name.isdigit():
            continue
        for game_dir in sorted(season_dir.iterdir()):
            if not game_dir.is_dir() or not game_dir.name.isdigit():
                continue
            stats = game_dir / "stats.json"
            if stats.is_file():
                yield int(season_dir.name), int(game_dir.name), stats


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _parse_played_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def collect_history_games(
    root: Path | None = None, *, include_did_not_play: bool = False
) -> dict[int, tuple[HistoryGame, ...]]:
    """Scan Corpus G and return per-player prior games ordered oldest first.

    ``didNotPlay`` rows are excluded by default: a scratch carries no box value
    signal and would drag every mean toward zero.
    """

    collected: dict[int, list[HistoryGame]] = {}
    for season, game_id, stats_path in iter_corpus_g_stats(root):
        payload: Any = json.loads(stats_path.read_text())
        if not isinstance(payload, dict):
            continue
        boxes = payload.get("playerBoxScores")
        if not isinstance(boxes, list):
            continue
        for box in boxes:
            if not isinstance(box, dict):
                continue
            player_id = box.get("playerId")
            if not isinstance(player_id, int) or isinstance(player_id, bool):
                continue
            if box.get("didNotPlay") is True and not include_did_not_play:
                continue
            box_value = _float_or_none(box.get("value"))
            played_at = _parse_played_at(box.get("dateTime"))
            team_id = box.get("teamId")
            if box_value is None or played_at is None or not isinstance(team_id, int):
                continue
            position = box.get("position")
            collected.setdefault(player_id, []).append(
                HistoryGame(
                    season=season,
                    game_id=game_id,
                    played_at=played_at,
                    position=position if isinstance(position, str) else "",
                    team_id=team_id,
                    box_value=box_value,
                    fantasy_points_fanduel=_float_or_none(box.get("fantasyPointsFanduel")),
                )
            )
    return {
        player_id: tuple(sorted(games, key=lambda g: (g.played_at, g.game_id)))
        for player_id, games in collected.items()
    }


def summarize_history(player_id: int, games: Sequence[HistoryGame]) -> PlayerHistory:
    """Reduce ordered prior games to the aggregate the projection stage needs."""

    if not games:
        raise ValueError("history_requires_at_least_one_game")
    values = tuple(game.box_value for game in games)
    return PlayerHistory(
        player_id=player_id,
        games=len(games),
        mean_box_value=sum(values) / len(values),
        max_box_value=max(values),
        min_box_value=min(values),
        last_box_value=values[-1],
        last_played_at=games[-1].played_at,
        seasons=tuple(sorted({game.season for game in games})),
        values=values,
    )


def build_history_index(
    root: Path | None = None, *, include_did_not_play: bool = False
) -> dict[int, PlayerHistory]:
    """Return ``player_id -> PlayerHistory`` for every player seen in Corpus G."""

    return {
        player_id: summarize_history(player_id, games)
        for player_id, games in collect_history_games(
            root, include_did_not_play=include_did_not_play
        ).items()
    }


def join_history(
    candidates: Iterable[Candidate], index: Mapping[int, PlayerHistory]
) -> tuple[CandidateRow, ...]:
    """Pair each live candidate with its history, keyed strictly on Real id.

    Team and position always come from the live candidate. Corpus G team ids
    are historical and are never used to place a player on a current roster.
    """

    return tuple(
        CandidateRow(candidate=candidate, history=index.get(candidate.player_id))
        for candidate in candidates
    )


def load_candidates(
    path: Path | str | None = None,
    *,
    contest_id: int = LIVE_CONTEST_ID,
    root: Path | None = None,
    with_history: bool = True,
) -> tuple[CandidateRow, ...]:
    """Load a saved slate and return its candidates joined to Corpus G history.

    This is the entry point for the projection stage. Pass ``with_history=False``
    to skip the Corpus G scan when only the live pool is needed.
    """

    slate = load_slate(path, contest_id=contest_id)
    index = build_history_index(root) if with_history else {}
    return join_history(slate.candidates, index)


# --------------------------------------------------------------------------
# Live refresh
# --------------------------------------------------------------------------


def live_artifact_name(contest_id: int, captured_at: datetime) -> str:
    """Return the filename for a live capture, colon-free for every filesystem."""

    stamp = utc(captured_at).strftime("%Y%m%dT%H%M%SZ")
    return f"slate_{contest_id}_live_{stamp}.json"


async def collect_live_slate(
    *,
    contest_id: int = LIVE_CONTEST_ID,
    day: date = LIVE_DAY,
    root: Path | None = None,
    timeout_s: float = 25.0,
) -> Slate:
    """Re-collect the eligible pool from the provider. Read-only GETs only."""

    from nfl_oracle.ingest.realsports import headers_or_capture

    base = root or project_root()
    headers = await headers_or_capture()
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        reader = NFLReader(client, headers, ObservationStore(observations_dir(base)))
        return await reader.collect(day, contest_id=contest_id)


async def refresh_live_slate(
    *,
    contest_id: int = LIVE_CONTEST_ID,
    day: date = LIVE_DAY,
    root: Path | None = None,
    write: bool = True,
) -> tuple[Slate, Path | None]:
    """Collect the live pool and persist it as a timestamped artifact."""

    slate = await collect_live_slate(contest_id=contest_id, day=day, root=root)
    if not write:
        return slate, None
    target = artifacts_dir(root) / live_artifact_name(contest_id, slate.captured_at)
    atomic_write_json(target, slate.model_dump(mode="json"), mode=0o600)
    return slate, target


def refresh_live_slate_sync(
    *,
    contest_id: int = LIVE_CONTEST_ID,
    day: date = LIVE_DAY,
    root: Path | None = None,
    write: bool = True,
) -> tuple[Slate, Path | None]:
    """Synchronous wrapper around :func:`refresh_live_slate`."""

    return asyncio.run(refresh_live_slate(contest_id=contest_id, day=day, root=root, write=write))


# --------------------------------------------------------------------------
# Diffing two captures
# --------------------------------------------------------------------------


class PlayerRef(Record):
    """Minimal identity for reporting a pool change."""

    player_id: int
    name: str
    position: str
    team: str
    injury_status: str | None
    card_boost: float


class InjuryChange(Record):
    """One player's injury status changing between two captures."""

    player_id: int
    name: str
    position: str
    team: str
    before: str | None
    after: str | None


class BoostChange(Record):
    """One player's assigned card boost changing between two captures."""

    player_id: int
    name: str
    team: str
    before: float
    after: float


class SlateDiff(Record):
    """Difference between an older and a newer capture of the same contest."""

    contest_id: int
    before_captured_at: datetime
    after_captured_at: datetime
    before_count: int
    after_count: int
    added: tuple[PlayerRef, ...]
    removed: tuple[PlayerRef, ...]
    injury_changes: tuple[InjuryChange, ...]
    boost_changes: tuple[BoostChange, ...]
    nonzero_boosts: tuple[PlayerRef, ...]
    lock_changed: bool

    @property
    def zero_boost_regime(self) -> bool:
        """True when the newer capture assigns every candidate a zero boost."""

        return not self.nonzero_boosts


def _ref(candidate: Candidate) -> PlayerRef:
    return PlayerRef(
        player_id=candidate.player_id,
        name=candidate.name,
        position=candidate.position,
        team=candidate.team,
        injury_status=candidate.injury_status,
        card_boost=candidate.card_boost,
    )


def diff_slates(before: Slate, after: Slate) -> SlateDiff:
    """Compare two captures of the same contest, keyed on Real player id."""

    if before.contest.contest_id != after.contest.contest_id:
        raise ValueError("diff_requires_same_contest")
    old = {c.player_id: c for c in before.candidates}
    new = {c.player_id: c for c in after.candidates}
    injury: list[InjuryChange] = []
    boosts: list[BoostChange] = []
    for player_id in sorted(set(old) & set(new)):
        was, now = old[player_id], new[player_id]
        if was.injury_status != now.injury_status:
            injury.append(
                InjuryChange(
                    player_id=player_id,
                    name=now.name,
                    position=now.position,
                    team=now.team,
                    before=was.injury_status,
                    after=now.injury_status,
                )
            )
        if was.card_boost != now.card_boost:
            boosts.append(
                BoostChange(
                    player_id=player_id,
                    name=now.name,
                    team=now.team,
                    before=was.card_boost,
                    after=now.card_boost,
                )
            )
    return SlateDiff(
        contest_id=after.contest.contest_id,
        before_captured_at=before.captured_at,
        after_captured_at=after.captured_at,
        before_count=len(before.candidates),
        after_count=len(after.candidates),
        added=tuple(_ref(new[pid]) for pid in sorted(set(new) - set(old))),
        removed=tuple(_ref(old[pid]) for pid in sorted(set(old) - set(new))),
        injury_changes=tuple(injury),
        boost_changes=tuple(boosts),
        nonzero_boosts=tuple(_ref(new[pid]) for pid in sorted(new) if new[pid].card_boost != 0.0),
        lock_changed=(
            before.contest.is_locked != after.contest.is_locked
            or before.contest.is_finalized != after.contest.is_finalized
        ),
    )


def lock_state(slate: Slate) -> dict[str, Any]:
    """Return the capture's lock facts without applying any staleness gate."""

    kickoff = min(game.kickoff_at for game in slate.games)
    now = datetime.now(UTC)
    return {
        "contest_id": slate.contest.contest_id,
        "captured_at": slate.captured_at.isoformat(),
        "is_locked": slate.contest.is_locked,
        "is_finalized": slate.contest.is_finalized,
        "provider_lock_at": (
            slate.contest.provider_lock_at.isoformat()
            if slate.contest.provider_lock_at is not None
            else None
        ),
        "earliest_kickoff_at": kickoff.isoformat(),
        "cutoff_at": slate.cutoff().isoformat(),
        "seconds_to_cutoff": (slate.cutoff() - now).total_seconds(),
        "game_statuses": {game.game_id: game.status for game in slate.games},
    }
