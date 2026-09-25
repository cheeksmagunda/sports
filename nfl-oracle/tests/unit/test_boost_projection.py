"""Boost-aware projection signal pins for Sunday win-ready (#327)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nfl_oracle.recommendations.boost_projection import (
    DEFAULT_BOOST_SIGNAL_PER_POINT,
    apply_boost_aware_projections,
)
from nfl_oracle.recommendations.model import Projection
from nfl_oracle.recommendations.schema import (
    Candidate,
    Contest,
    EvidenceClock,
    Game,
    Slate,
)

NOW = datetime(2026, 9, 27, 16, 0, tzinfo=UTC)


def _slate(*, boost: float, regime: str = "provider_boosts_present") -> Slate:
    clock = EvidenceClock(source_available_at=NOW, captured_at=NOW)
    game = Game(
        game_id=1,
        season=2026,
        home_team_id=1,
        away_team_id=2,
        home_team="DAL",
        away_team="PHI",
        kickoff_at=NOW + timedelta(hours=1),
        status="scheduled",
    )
    candidates = (
        Candidate(
            player_id=1,
            game_id=1,
            team_id=1,
            name="Boosted",
            position="WR",
            team="DAL",
            opponent="PHI",
            injury_status="Active",
            card_boost=boost,
            clock=clock,
        ),
        Candidate(
            player_id=2,
            game_id=1,
            team_id=2,
            name="Flat",
            position="RB",
            team="PHI",
            opponent="DAL",
            injury_status="Active",
            card_boost=0.0,
            clock=clock,
        ),
    )
    nonzero = 1 if boost > 0 else 0
    return Slate(
        contest=Contest(
            contest_id=99,
            day=NOW.date(),
            end_day=NOW.date(),
            slot_multipliers=(2.0, 1.8, 1.6, 1.4, 1.2),
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="a" * 64,
        ),
        games=(game,),
        candidates=candidates,
        captured_at=NOW,
        source_hashes=("b" * 64,),
        pool_roster_count=2,
        pool_search_matched_count=2,
        pool_unmatched_ids=(),
        pool_complete=True,
        boost_regime=regime,  # type: ignore[arg-type]
        boost_nonzero_count=nonzero,
        boost_max=boost,
    )


def _projection(player_id: int, mean: float) -> Projection:
    return Projection(
        player_id=player_id,
        mean=mean,
        conditional_mean=mean,
        availability_probability=1.0,
        stddev=0.5,
        prior_games=5,
        samples=(mean - 0.1, mean, mean + 0.1),
        provenance=("test",),
    )


def test_boost_signal_lifts_boosted_player_only() -> None:
    slate = _slate(boost=3.0)
    projections = (_projection(1, 4.0), _projection(2, 5.0))
    adjusted = apply_boost_aware_projections(projections, slate)
    by_id = {p.player_id: p for p in adjusted}
    lift = DEFAULT_BOOST_SIGNAL_PER_POINT * 3.0
    assert by_id[1].conditional_mean == 4.0 + lift
    assert by_id[1].mean == 4.0 + lift
    assert by_id[1].samples == (4.0 - 0.1 + lift, 4.0 + lift, 4.0 + 0.1 + lift)
    assert "boost_aware_projection_signal" in by_id[1].provenance
    assert by_id[2].conditional_mean == 5.0
    assert by_id[2].provenance == ("test",)


def test_zero_boost_regime_is_noop() -> None:
    slate = _slate(boost=0.0, regime="zero_boost")
    projections = (_projection(1, 4.0), _projection(2, 5.0))
    adjusted = apply_boost_aware_projections(projections, slate)
    assert [p.conditional_mean for p in adjusted] == [4.0, 5.0]


def test_disabled_signal_is_noop() -> None:
    slate = _slate(boost=3.0)
    projections = (_projection(1, 4.0), _projection(2, 5.0))
    adjusted = apply_boost_aware_projections(
        projections, slate, signal_per_boost_point=0.0
    )
    assert [p.conditional_mean for p in adjusted] == [4.0, 5.0]
