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
    assert model.selected_estimator in {"ridge", "player_prior", "position_mean", "global_mean"}
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
