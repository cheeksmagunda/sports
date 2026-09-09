"""Historical zero-boost projection backtests over Corpus G player games."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from statistics import mean

from nfl_oracle.contests.schema import OBSERVED_SLOT_MULTIPLIERS
from nfl_oracle.valuelaw.candidates import HistoryGame
from nfl_oracle.valuelaw.project import ewma


@dataclass(frozen=True)
class GameBacktestResult:
    game_id: int
    played_at: datetime
    predicted_player_ids: tuple[int, ...]
    hindsight_player_ids: tuple[int, ...]
    committed_score: float
    hindsight_score: float
    capture_ratio: float


@dataclass(frozen=True)
class BacktestSummary:
    n_games: int
    mean_capture_ratio: float | None
    median_capture_ratio: float | None
    min_capture_ratio: float | None
    max_capture_ratio: float | None


def _position_prior(
    history: Mapping[int, Sequence[HistoryGame]], played_at: datetime
) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for games in history.values():
        for game in games:
            if game.played_at < played_at:
                values[game.position].append(game.box_value)
    return {position: mean(samples) for position, samples in values.items() if samples}


def _project(
    player_id: int,
    position: str,
    prior_games: Sequence[HistoryGame],
    priors: Mapping[str, float],
    *,
    min_player_games: int,
    decay: float,
) -> float | None:
    if len(prior_games) >= min_player_games:
        return ewma(tuple(game.box_value for game in prior_games), decay=decay)
    return priors.get(position)


def backtest_zero_boost_projection_from_history_index(
    history: Mapping[int, Sequence[HistoryGame]],
    *,
    min_player_games: int = 3,
    decay: float = 0.9,
    slot_multipliers: Sequence[float] = OBSERVED_SLOT_MULTIPLIERS,
) -> tuple[GameBacktestResult, ...]:
    """Replay games from a ``player_id -> HistoryGame`` index."""

    if len(slot_multipliers) != 5:
        raise ValueError("five_slots_required")
    events: list[tuple[int, HistoryGame]] = []
    for player_id, player_games in history.items():
        for game in player_games:
            events.append((player_id, game))
    grouped: dict[int, list[tuple[int, HistoryGame]]] = defaultdict(list)
    for player_id, game in events:
        grouped[game.game_id].append((player_id, game))

    results: list[GameBacktestResult] = []
    for game_id, rows in sorted(
        grouped.items(), key=lambda item: min(g.played_at for _, g in item[1])
    ):
        played_at = min(game.played_at for _, game in rows)
        priors = _position_prior(history, played_at)
        projected: list[tuple[float, int, HistoryGame]] = []
        for player_id, game in rows:
            prior_games = tuple(g for g in history[player_id] if g.played_at < played_at)
            projection = _project(
                player_id,
                game.position,
                prior_games,
                priors,
                min_player_games=min_player_games,
                decay=decay,
            )
            if projection is not None:
                projected.append((projection, player_id, game))
        if len(projected) < 5 or len(rows) < 5:
            continue
        chosen = sorted(projected, key=lambda item: (-item[0], item[1]))[:5]
        actual_by_player = {player_id: game.box_value for player_id, game in rows}
        committed = sum(
            actual_by_player[player_id] * float(slot_multipliers[index])
            for index, (_projection, player_id, _game) in enumerate(chosen)
        )
        hindsight = sorted(rows, key=lambda item: (-item[1].box_value, item[0]))[:5]
        hindsight_score = sum(
            game.box_value * float(slot_multipliers[index])
            for index, (_player_id, game) in enumerate(hindsight)
        )
        if hindsight_score <= 0:
            continue
        results.append(
            GameBacktestResult(
                game_id=game_id,
                played_at=played_at,
                predicted_player_ids=tuple(player_id for _projection, player_id, _game in chosen),
                hindsight_player_ids=tuple(player_id for player_id, _game in hindsight),
                committed_score=committed,
                hindsight_score=hindsight_score,
                capture_ratio=committed / hindsight_score,
            )
        )
    return tuple(results)


def summarize_backtest(results: Sequence[GameBacktestResult]) -> BacktestSummary:
    captures = sorted(result.capture_ratio for result in results)
    if not captures:
        return BacktestSummary(
            n_games=0,
            mean_capture_ratio=None,
            median_capture_ratio=None,
            min_capture_ratio=None,
            max_capture_ratio=None,
        )
    middle = len(captures) // 2
    median = (
        captures[middle] if len(captures) % 2 else (captures[middle - 1] + captures[middle]) / 2
    )
    return BacktestSummary(
        n_games=len(captures),
        mean_capture_ratio=mean(captures),
        median_capture_ratio=median,
        min_capture_ratio=captures[0],
        max_capture_ratio=captures[-1],
    )
