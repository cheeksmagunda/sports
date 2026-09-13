"""The decision path must survive a full Sunday, not just a one-game slate.

Every other slate fixture in this suite carries a single game and a handful of
candidates. A real NFL Sunday is thirteen games and roughly nineteen hundred
rostered players, a shape the freeze path had never been exercised against, and
it failed in production on exactly that shape while single-game rehearsals
passed. These tests build the wide slate and drive predict -> optimize over it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nfl_oracle.recommendations.model import HistoricalPerformance, fit_model, predict
from nfl_oracle.recommendations.optimizer import optimize
from nfl_oracle.recommendations.pipeline import ScoringPolicy
from nfl_oracle.recommendations.schema import Candidate, Contest, EvidenceClock, Game, Slate

BASE = datetime(2025, 9, 1, 12, tzinfo=UTC)
GAMES = 13
PER_TEAM = 24
POSITIONS = ("QB", "RB", "WR", "TE", "K", "DL", "LB", "DB")


def _history(players: int) -> list[HistoricalPerformance]:
    """Prior weeks for every player except a deliberately history-free tail."""

    result: list[HistoricalPerformance] = []
    for week in range(6):
        kickoff = BASE + timedelta(days=week)
        for player in range(1, players + 1):
            # The last tenth of the pool are rookies: rostered, never played.
            # They must be projected from position priors, never dropped and
            # never allowed to refuse the whole freeze.
            if player % 10 == 0:
                continue
            result.append(
                HistoricalPerformance(
                    player_id=player,
                    external_id=f"p-{player}",
                    game_id=100_000 + week * 1000 + player,
                    position=POSITIONS[player % len(POSITIONS)],
                    kickoff_at=kickoff,
                    available_at=kickoff + timedelta(hours=2),
                    captured_at=kickoff + timedelta(hours=3),
                    value=float((player % 7) + week * 0.5),
                    did_not_play=False,
                )
            )
    return result


def _sunday_slate(decision: datetime) -> Slate:
    """Thirteen games with staggered kickoffs, as a real Sunday arrives."""

    clock = EvidenceClock(source_available_at=decision, captured_at=decision)
    games = []
    candidates = []
    player_id = 0
    for index in range(GAMES):
        # Noon, afternoon and night windows, all still ahead of the decision.
        offset = 4 + (index // 5) * 3
        game = Game(
            game_id=19_000 + index,
            season=2025,
            kickoff_at=decision + timedelta(hours=offset),
            home_team_id=index * 2 + 1,
            away_team_id=index * 2 + 2,
            home_team=f"H{index}",
            away_team=f"A{index}",
            status="scheduled",
        )
        games.append(game)
        for side in range(2):
            for _ in range(PER_TEAM):
                player_id += 1
                candidates.append(
                    Candidate(
                        player_id=player_id,
                        game_id=game.game_id,
                        team_id=game.home_team_id if side == 0 else game.away_team_id,
                        name=f"P{player_id}",
                        position=POSITIONS[player_id % len(POSITIONS)],
                        team=game.home_team if side == 0 else game.away_team,
                        opponent=game.away_team if side == 0 else game.home_team,
                        injury_status="Active",
                        card_boost=0,
                        clock=clock,
                    )
                )
    return Slate(
        contest=Contest(
            contest_id=2154,
            day=decision.date(),
            end_day=decision.date(),
            slot_multipliers=(2, 1.8, 1.6, 1.4, 1.2),
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="a" * 64,
        ),
        games=tuple(games),
        candidates=tuple(candidates),
        captured_at=decision,
        source_hashes=("b" * 64,),
        pool_roster_count=len(candidates),
        pool_search_matched_count=len(candidates),
    )


def test_full_sunday_slate_produces_five_picks() -> None:
    decision = BASE + timedelta(days=8)
    slate = _sunday_slate(decision)
    assert len(slate.games) == GAMES
    history = _history(len(slate.candidates))
    model = fit_model(history, trained_at=decision)

    projections = predict(slate, model, history, decision_at=decision)

    # Every rostered player is graded, including those with no history at all.
    assert len(projections) == len(slate.candidates)
    assert all(p.samples for p in projections)

    recommendation = optimize(
        slate,
        projections,
        decision_at=decision,
        scoring_policy=ScoringPolicy(),
    )
    assert len(recommendation.picks) == 5
    assert [pick.slot for pick in recommendation.picks] == [1, 2, 3, 4, 5]


def test_players_without_history_are_graded_not_excluded() -> None:
    """A rookie is eligible with an inflated uncertainty, never a refusal."""

    decision = BASE + timedelta(days=8)
    slate = _sunday_slate(decision)
    history = _history(len(slate.candidates))
    model = fit_model(history, trained_at=decision)

    projections = {p.player_id: p for p in predict(slate, model, history, decision_at=decision)}

    rookies = [pid for pid in projections if pid % 10 == 0]
    veterans = [pid for pid in projections if pid % 10 != 0]
    assert rookies, "fixture must contain history-free players"

    for pid in rookies:
        projection = projections[pid]
        assert projection.samples, "a rookie must still carry a distribution"
        assert projection.availability_probability > 0, "a rookie must stay eligible"

    # Absent evidence must widen the distribution rather than silently
    # substituting a confident number.
    widest_veteran = max(projections[pid].stddev for pid in veterans)
    assert min(projections[pid].stddev for pid in rookies) >= widest_veteran
    assert all(projections[pid].prior_games == 0 for pid in rookies)
