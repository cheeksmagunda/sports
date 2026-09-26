from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from nfl_oracle.recommendations.model import (
    ContextAdjustment,
    HistoricalPerformance,
    attach_enrichment,
    fit_model,
    predict,
)
from nfl_oracle.recommendations.optimizer import (
    FieldObservation,
    OptimizerConfig,
    ScoringPolicy,
    optimize,
)
from nfl_oracle.recommendations.schema import (
    Candidate,
    Contest,
    EvidenceClock,
    Game,
    Slate,
    fingerprint,
)

BASE = datetime(2025, 9, 1, 12, tzinfo=UTC)


def history_rows() -> list[HistoricalPerformance]:
    rows: list[HistoricalPerformance] = []
    for game in range(6):
        kickoff = BASE + timedelta(days=game)
        for player in range(1, 7):
            rows.append(
                HistoricalPerformance(
                    player_id=player,
                    game_id=100 + game,
                    position="QB" if player == 1 else "WR",
                    role="passing" if player == 1 else "receiving",
                    kickoff_at=kickoff,
                    available_at=kickoff + timedelta(hours=2),
                    captured_at=kickoff + timedelta(hours=3),
                    value=float(player + game),
                    opportunity=float(player + game),
                    did_not_play=player == 6 and game % 2 == 0,
                    context_features={"weather_index": float(game)},
                    context_clock=EvidenceClock(
                        source_available_at=kickoff - timedelta(hours=2),
                        captured_at=kickoff - timedelta(hours=1),
                    ),
                )
            )
    return rows


def slate(*, one_team: bool = False, one_game: bool = False) -> Slate:
    decision = BASE + timedelta(days=8)
    clock = EvidenceClock(source_available_at=decision, captured_at=decision)
    games = (
        Game(
            game_id=200,
            season=2025,
            kickoff_at=decision + timedelta(hours=4),
            home_team_id=10,
            away_team_id=11,
            home_team="A",
            away_team="B",
            status="scheduled",
        ),
    )
    if not one_game:
        games += (
            Game(
                game_id=201,
                season=2025,
                kickoff_at=decision + timedelta(hours=5),
                home_team_id=12,
                away_team_id=13,
                home_team="C",
                away_team="D",
                status="scheduled",
            ),
        )
    candidates = tuple(
        Candidate(
            player_id=player,
            game_id=games[0 if one_game else player % 2].game_id,
            team_id=(10 if one_team else (10 + (2 * (0 if one_game else player % 2)) + player % 2)),
            name=f"P{player}",
            position="WR",
            team="A",
            opponent="B",
            injury_status="Active",
            card_boost=0.5 if player == 1 else 0,
            clock=clock,
        )
        for player in range(1, 7)
    )
    return Slate(
        contest=Contest(
            contest_id=900,
            day=decision.date(),
            end_day=decision.date(),
            slot_multipliers=(2, 1.8, 1.6, 1.4, 1.2),
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="a" * 64,
        ),
        games=games,
        candidates=candidates,
        captured_at=decision,
        source_hashes=("b" * 64,),
        pool_roster_count=len(candidates),
        pool_search_matched_count=len(candidates),
    )


def projections(slate_value: Slate):
    from nfl_oracle.recommendations.model import Projection

    return tuple(
        Projection(
            player_id=c.player_id,
            mean=float(c.player_id),
            conditional_mean=float(c.player_id),
            stddev=1,
            availability_probability=1,
            prior_games=5,
            samples=(float(c.player_id), float(c.player_id) + 1),
            provenance=("test_estimate",),
        )
        for c in slate_value.candidates
    )


def test_chronological_model_has_hash_holdout_baselines_and_role_features() -> None:
    model = fit_model(history_rows(), trained_at=BASE + timedelta(days=10))
    assert model.model_fingerprint == fingerprint(model.model_dump(mode="json"))
    assert len(model.coefficients) == 7 + 2
    assert model.evaluation["kind"] == "retrospective_source_clock_frozen_holdout"
    assert "global_mean_mae" in model.evaluation
    assert "position_mean_mae" in model.evaluation
    assert "player_prior_mae" in model.evaluation
    assert model.training_fingerprint
    assert model.selected_estimator in {"ridge", "position_mean", "global_mean"}
    assert model.evaluation["selected_estimator"] == model.selected_estimator


def test_retrospective_enrichment_preserves_snapshot_clock_and_disclosure() -> None:
    rows = history_rows()
    source_clock = EvidenceClock(
        source_available_at=BASE + timedelta(days=1, hours=1),
        captured_at=BASE + timedelta(days=1, hours=2),
    )

    enrichment = SimpleNamespace(
        rows=(
            SimpleNamespace(
                player_id=rows[0].player_id,
                game_id=rows[0].game_id,
                features={"weather_temp_f": 72.0, "depth_rank": 1.0},
                clock=source_clock,
                source_hashes=("c" * 64,),
                evidence_mode="retrospective_reconstructed",
            ),
        )
    )

    attached = attach_enrichment(rows, enrichment)
    assert attached[0].context_evidence_mode == "retrospective_reconstructed"
    assert attached[0].context_clock == source_clock
    assert attached[0].context_source_hashes == ("c" * 64,)
    model = fit_model(attached, trained_at=BASE + timedelta(days=10))
    assert model.evaluation["context_evidence_disclosure"] == (
        "retrospective_reconstructed_context_included"
    )
    assert "weather_temp_f" in model.feature_coverage


def test_future_context_snapshot_is_rejected() -> None:
    rows = history_rows()

    enrichment = SimpleNamespace(
        rows=(
            SimpleNamespace(
                player_id=rows[0].player_id,
                game_id=rows[0].game_id,
                features={"weather_temp_f": 72.0},
                clock=EvidenceClock(
                    source_available_at=BASE + timedelta(days=20),
                    captured_at=BASE + timedelta(days=20),
                ),
                source_hashes=(),
                evidence_mode="retrospective_reconstructed",
            ),
        )
    )

    attached = attach_enrichment(rows, enrichment)
    with pytest.raises(ValueError, match="future_context_evidence"):
        fit_model(attached, trained_at=BASE + timedelta(days=10))


def test_prediction_uses_availability_and_rejects_future_model() -> None:
    model = fit_model(history_rows(), trained_at=BASE + timedelta(days=10))
    target = slate(one_game=True)
    with pytest.raises(ValueError, match="future_model"):
        predict(target, model, history_rows(), decision_at=BASE + timedelta(days=8))


def test_prediction_uses_historical_external_identity_when_real_id_is_new() -> None:
    history = [
        row.model_copy(update={"external_id": f"gsis-{row.player_id}"}) for row in history_rows()
    ]
    model = fit_model(history, trained_at=BASE + timedelta(days=7))
    target = slate(one_game=True)
    current = target.candidates[0].model_copy(update={"player_id": 999})
    target = target.model_copy(
        update={
            "candidates": (current, *target.candidates[1:]),
            "pool_roster_count": 6,
            "pool_search_matched_count": 6,
        }
    )
    adjustment = {
        999: ContextAdjustment(
            external_id="gsis-1",
            clock=current.clock,
        )
    }
    projection = predict(
        target,
        model,
        history,
        decision_at=BASE + timedelta(days=8),
        context=adjustment,
    )[0]
    assert projection.prior_games == 6
    assert "context_unavailable" not in projection.provenance


def test_optimizer_clamps_over_cap_boost_instead_of_crashing() -> None:
    target = slate(one_team=True, one_game=True)
    base = target.candidates[0]
    over_cap = Candidate.model_construct(
        player_id=base.player_id,
        game_id=base.game_id,
        team_id=base.team_id,
        name=base.name,
        position=base.position,
        team=base.team,
        opponent=base.opponent,
        injury_status=base.injury_status,
        card_boost=4.5,
        boost_source=base.boost_source,
        clock=base.clock,
    )
    target = Slate.model_construct(
        contest=target.contest,
        games=target.games,
        candidates=(over_cap,) + target.candidates[1:],
        captured_at=target.captured_at,
        source_hashes=target.source_hashes,
        pool_roster_count=target.pool_roster_count,
        pool_search_matched_count=target.pool_search_matched_count,
        pool_unmatched_ids=target.pool_unmatched_ids,
        pool_complete=target.pool_complete,
        boost_regime=target.boost_regime,
        boost_nonzero_count=target.boost_nonzero_count,
        boost_max=4.5,
    )
    result = optimize(
        target,
        projections(target),
        decision_at=BASE + timedelta(days=8),
        scoring_policy=ScoringPolicy(negative_branch="unverified"),
        config=OptimizerConfig(simulations=100),
    )
    assert len(result.picks) == 5


def test_optimizer_returns_five_unique_picks_and_reports_relaxed_diversity() -> None:
    target = slate(one_team=True, one_game=True)
    result = optimize(
        target,
        projections(target),
        decision_at=BASE + timedelta(days=8),
        scoring_policy=ScoringPolicy(negative_branch="unverified"),
        config=OptimizerConfig(min_distinct_teams=3, min_distinct_games=2, simulations=100),
    )
    assert len(result.picks) == 5
    assert len({pick.player_id for pick in result.picks}) == 5
    assert result.requested_distinct_teams == 3
    assert result.required_distinct_teams == 1
    assert result.required_distinct_games == 1
    assert result.diversity_relaxed is True
    assert result.total_value == result.objective_value


def test_scoring_law_is_additive_and_total_value_is_the_only_objective() -> None:
    assert ScoringPolicy().score(10, 2, 3) == 50
    assert ScoringPolicy().score(-10, 2, 3) == -50
    target = slate(one_game=True)
    result = optimize(
        target,
        projections(target),
        decision_at=BASE + timedelta(days=8),
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(simulations=100),
    )
    assert result.objective == "total_value"
    assert result.total_value == result.objective_value


def test_partial_measured_field_keeps_unknown_players_estimated() -> None:
    target = slate(one_game=True)
    decision = BASE + timedelta(days=8)
    field = FieldObservation(
        clock=EvidenceClock(source_available_at=decision, captured_at=decision),
        entry_count=5,
        player_counts={6: 5},
        provenance="provider_top_players_partial",
        coverage="partial",
    )
    result = optimize(
        target,
        projections(target),
        decision_at=decision,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(simulations=100),
        field=field,
    )
    assert any(p.player_id == 6 and p.ownership_source == "measured_prelock" for p in result.picks)
    assert any(
        p.player_id != 6 and p.ownership_source == "estimated_projection_softmax"
        for p in result.picks
    )


def test_contest_utility_formula() -> None:
    from nfl_oracle.recommendations.optimizer import contest_utility

    assert contest_utility(10, 12, 0.5, upside_weight=0, field_weight=0) == 10
    assert contest_utility(10, 12, 0.5, upside_weight=0.5, field_weight=0) == 10 + 0.5 * 12
    assert contest_utility(10, 12, 0.5, upside_weight=0, field_weight=0.2) == 10 + 0.2 * 10 * 0.5


def _custom_projections(
    slate_value: Slate,
    *,
    means: dict[int, float],
    samples: dict[int, tuple[float, ...]],
):
    from nfl_oracle.recommendations.model import Projection

    return tuple(
        Projection(
            player_id=c.player_id,
            mean=means[c.player_id],
            conditional_mean=means[c.player_id],
            stddev=1,
            availability_probability=1,
            prior_games=5,
            samples=samples[c.player_id],
            provenance=("test_estimate",),
        )
        for c in slate_value.candidates
    )


def test_upside_weight_prefers_higher_p90_when_means_close() -> None:
    target = slate(one_game=True)
    # Players 1-4 are anchors. 5 is slightly higher E; 6 matches lower mean with fat tail.
    means = {1: 10.0, 2: 9.0, 3: 8.0, 4: 7.0, 5: 6.2, 6: 6.0}
    samples = {
        1: (10.0,) * 5,
        2: (9.0,) * 5,
        3: (8.0,) * 5,
        4: (7.0,) * 5,
        5: (6.2,) * 5,
        6: (0.0, 0.0, 6.0, 12.0, 12.0),  # mean 6.0, higher p90
    }
    projs = _custom_projections(target, means=means, samples=samples)
    decision = BASE + timedelta(days=8)
    baseline = optimize(
        target,
        projs,
        decision_at=decision,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(
            simulations=200,
            upside_weight=0,
            field_weight=0,
            min_distinct_teams=1,
            min_distinct_games=1,
            seed=7,
        ),
    )
    upside = optimize(
        target,
        projs,
        decision_at=decision,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(
            simulations=200,
            upside_weight=2.0,
            field_weight=0,
            min_distinct_teams=1,
            min_distinct_games=1,
            seed=7,
        ),
    )
    baseline_ids = {p.player_id for p in baseline.picks}
    upside_ids = {p.player_id for p in upside.picks}
    assert 6 not in baseline_ids
    assert 6 in upside_ids
    assert upside.simulated_p90 >= baseline.simulated_p90


def test_field_weight_changes_selection_when_field_beat_differs() -> None:
    from nfl_oracle.recommendations.optimizer import contest_utility

    # Same expected, different field-beat rates: raising field_weight flips the ranking.
    chalk_e, chalk_beat = 66.0, 0.05
    lev_e, lev_beat = 65.9, 0.45
    assert contest_utility(
        chalk_e, chalk_e, chalk_beat, upside_weight=0, field_weight=0
    ) > contest_utility(lev_e, lev_e, lev_beat, upside_weight=0, field_weight=0)
    assert contest_utility(
        lev_e, lev_e, lev_beat, upside_weight=0, field_weight=2.0
    ) > contest_utility(chalk_e, chalk_e, chalk_beat, upside_weight=0, field_weight=2.0)

    # optimize() must thread field_weight into contest_utility (not a dead knob).
    target = slate(one_game=True)
    decision = BASE + timedelta(days=8)
    seen: list[float] = []
    import nfl_oracle.recommendations.optimizer as opt_mod

    real = opt_mod.contest_utility

    def spy(expected, p90, field_win_rate, *, upside_weight, field_weight):
        seen.append(field_weight)
        return real(
            expected,
            p90,
            field_win_rate,
            upside_weight=upside_weight,
            field_weight=field_weight,
        )

    opt_mod.contest_utility = spy  # type: ignore[assignment]
    try:
        optimize(
            target,
            projections(target),
            decision_at=decision,
            scoring_policy=ScoringPolicy(),
            config=OptimizerConfig(
                simulations=100,
                upside_weight=0,
                field_weight=1.25,
                min_distinct_teams=1,
                min_distinct_games=1,
            ),
        )
    finally:
        opt_mod.contest_utility = real  # type: ignore[assignment]
    assert seen and all(w == 1.25 for w in seen)


def test_chalk_stud_survives_high_field_weight() -> None:
    target = slate(one_game=True)
    means = {1: 100.0, 2: 9.0, 3: 8.0, 4: 7.0, 5: 6.0, 6: 5.0}
    samples = {pid: (means[pid],) * 5 for pid in means}
    projs = _custom_projections(target, means=means, samples=samples)
    decision = BASE + timedelta(days=8)
    field = FieldObservation(
        clock=EvidenceClock(source_available_at=decision, captured_at=decision),
        entry_count=100,
        player_counts={1: 100, 2: 80, 3: 80, 4: 80, 5: 80, 6: 80},
        provenance="test_field",
        coverage="complete",
    )
    result = optimize(
        target,
        projs,
        decision_at=decision,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(
            simulations=200,
            upside_weight=0,
            field_weight=2.0,
            min_distinct_teams=1,
            min_distinct_games=1,
            seed=3,
        ),
        field=field,
    )
    assert 1 in {p.player_id for p in result.picks}
