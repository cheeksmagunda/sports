"""Integration coverage for issue #166: the live pick path under real boosts.

Before week 2's Thursday boost table goes live, this proves two independent
implementations of "pick the optimal five under score = value * (slot +
boost)" agree on the same non-uniform, non-zero boost table:

* ``nfl_oracle.recommendations.optimizer.optimize`` -- the production milp
  exact search over the live candidate pool.
* ``nfl_oracle.replay.harness.hindsight_best_lineup`` -- the already-tested,
  independently derived rearrangement-inequality DP used to grade finalized
  contests.

Team/game diversity is disabled on the optimizer side (min_distinct_teams=1,
min_distinct_games=1) because the replay DP has no such constraint; the pool
below is deliberately single-team/single-game so the two are solving exactly
the same combinatorial problem.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nfl_oracle.contests.parse import ParsedContest
from nfl_oracle.contests.schema import ContestRecord, DraftStatRow
from nfl_oracle.recommendations.model import Projection
from nfl_oracle.recommendations.optimizer import OptimizerConfig, ScoringPolicy, optimize
from nfl_oracle.recommendations.schema import Candidate, Contest, EvidenceClock, Game, Slate
from nfl_oracle.replay.harness import hindsight_best_lineup

BASE = datetime(2026, 9, 17, 12, tzinfo=UTC)
SLOTS = (2.0, 1.8, 1.6, 1.4, 1.2)
CONTEST_ID = 9001

# A real (non-uniform, non-zero) boost table: several candidates carry
# genuine leverage, not a uniform or all-zero table, so slot order is not
# simply descending projected value.
POOL: dict[int, tuple[float, float]] = {
    1: (12.0, 0.0),
    2: (11.0, 0.0),
    3: (10.0, 0.0),
    4: (9.0, 0.0),
    5: (8.0, 0.0),
    6: (7.9, 3.0),
    7: (6.0, 1.5),
    8: (5.0, 2.0),
    9: (4.0, 0.5),
    10: (3.0, 0.0),
}


def _slate() -> Slate:
    decision = BASE
    clock = EvidenceClock(source_available_at=decision, captured_at=decision)
    game = Game(
        game_id=500,
        season=2026,
        kickoff_at=decision + timedelta(hours=4),
        home_team_id=20,
        away_team_id=21,
        home_team="A",
        away_team="B",
        status="scheduled",
    )
    candidates = tuple(
        Candidate(
            player_id=pid,
            game_id=game.game_id,
            team_id=20,
            name=f"P{pid}",
            position="WR",
            team="A",
            opponent="B",
            injury_status="Active",
            card_boost=boost,
            clock=clock,
        )
        for pid, (_value, boost) in POOL.items()
    )
    return Slate(
        contest=Contest(
            contest_id=CONTEST_ID,
            day=decision.date(),
            end_day=decision.date(),
            slot_multipliers=SLOTS,
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="a" * 64,
        ),
        games=(game,),
        candidates=candidates,
        captured_at=decision,
        source_hashes=("b" * 64,),
        pool_roster_count=len(candidates),
        pool_search_matched_count=len(candidates),
    )


def _projections(slate_value: Slate) -> tuple[Projection, ...]:
    values = {pid: value for pid, (value, _boost) in POOL.items()}
    return tuple(
        Projection(
            player_id=c.player_id,
            mean=values[c.player_id],
            conditional_mean=values[c.player_id],
            stddev=0.0,
            availability_probability=1.0,
            prior_games=5,
            samples=(values[c.player_id], values[c.player_id]),
            provenance=("test_fixed_value",),
        )
        for c in slate_value.candidates
    )


def _parsed_contest() -> ParsedContest:
    draft_stats = tuple(
        DraftStatRow(
            contest_id=CONTEST_ID,
            player_id=pid,
            section="Highest value",
            card_boost=boost,
            value=value,
        )
        for pid, (value, boost) in POOL.items()
    )
    contest = ContestRecord(
        contest_id=CONTEST_ID,
        sport="nfl",
        day=BASE.date(),
        end_day=BASE.date(),
        lineup_size=5,
        slot_multipliers=SLOTS,
        entrants=1000,
        is_finalized=True,
        captured_at=BASE,
    )
    return ParsedContest(
        contest=contest,
        entries=(),
        draft_stats=draft_stats,
        missing_routes=(),
        law_verified=True,
    )


def test_optimizer_matches_replay_dp_under_nonuniform_boosts() -> None:
    slate = _slate()
    result = optimize(
        slate,
        _projections(slate),
        decision_at=BASE,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(min_distinct_teams=1, min_distinct_games=1, simulations=100),
    )
    assert result.boost_regime == "provider_boosts_present"
    assert result.boost_nonzero_count == 4
    assert result.boost_max == 3.0

    dp = hindsight_best_lineup(_parsed_contest())
    assert dp is not None

    naive_top5_by_value = (1, 2, 3, 4, 5)
    assert dp.player_ids != naive_top5_by_value  # boost genuinely changes the optimal set

    optimizer_ids = tuple(pick.player_id for pick in result.picks)
    assert optimizer_ids == dp.player_ids
    assert result.total_value == pytest.approx(dp.total_score, rel=1e-6)
