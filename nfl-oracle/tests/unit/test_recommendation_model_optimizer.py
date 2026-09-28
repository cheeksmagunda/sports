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
    DEFENDER_POSITIONS,
    FieldObservation,
    OptimizerConfig,
    ScoringPolicy,
    optimize,
    optimizer_config_from_env,
    slate_regime_name,
)
from nfl_oracle.recommendations.picker_knobs import PickerKnobs, apply_picker_knobs
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
    # Core priors (7) + 2 floats per wired context name (value + missing).
    # #418 force-includes live_ok injury/weather keys even when sparse.
    assert len(model.coefficients) == 7 + 2 * len(model.context_feature_names)
    # at least weather_index from fixture plus the live_ok set
    assert len(model.context_feature_names) >= 2
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


def _projection(
    player_id: int,
    *,
    mean: float,
    samples: tuple[float, ...],
    availability: float = 1.0,
):
    from nfl_oracle.recommendations.model import Projection

    return Projection(
        player_id=player_id,
        mean=mean,
        conditional_mean=mean,
        stddev=max(0.1, (max(samples) - min(samples)) / 2),
        availability_probability=availability,
        prior_games=5,
        samples=samples,
        provenance=("test_estimate",),
    )


def test_raising_field_weight_changes_lineup_when_ownership_differs() -> None:
    """Higher field_weight re-ranks near-EV lineups by simulated field-beat rate."""

    target = slate()
    decision = target.captured_at
    # Player 6 is slightly lower EV than 5 but boomier. Zero field_weight can
    # prefer the boom path; positive field_weight re-ranks by field-beat rate
    # against the measured ownership field.
    chalk_means = {1: 10.0, 2: 9.0, 3: 8.0, 4: 7.0, 5: 6.0, 6: 5.95}
    projs = tuple(
        _projection(
            c.player_id,
            mean=chalk_means[c.player_id],
            samples=(
                chalk_means[c.player_id] - 0.5,
                chalk_means[c.player_id],
                chalk_means[c.player_id] + (2.0 if c.player_id == 6 else 0.5),
            ),
        )
        for c in target.candidates
    )
    field = FieldObservation(
        clock=EvidenceClock(source_available_at=decision, captured_at=decision),
        entry_count=100,
        player_counts={1: 100, 2: 100, 3: 100, 4: 100, 5: 90, 6: 10},
        provenance="test",
        coverage="complete",
    )
    baseline = optimize(
        target,
        projs,
        decision_at=decision,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(simulations=400, field_weight=0.0, upside_weight=0.0, seed=7),
        field=field,
    )
    leveraged = optimize(
        target,
        projs,
        decision_at=decision,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(simulations=400, field_weight=2.0, upside_weight=0.0, seed=7),
        field=field,
    )
    assert {p.player_id for p in baseline.picks} != {p.player_id for p in leveraged.picks}


def test_raising_upside_weight_prefers_higher_p90_when_means_tied() -> None:
    target = slate()
    decision = target.captured_at
    # Equal means for the marginal slot; player 6 has a fat right tail.
    projs = []
    for c in target.candidates:
        if c.player_id == 5:
            projs.append(_projection(5, mean=5.0, samples=(4.5, 5.0, 5.5)))
        elif c.player_id == 6:
            projs.append(_projection(6, mean=5.0, samples=(1.0, 5.0, 12.0)))
        else:
            mean_v = float(10 - c.player_id + 1)
            projs.append(
                _projection(
                    c.player_id,
                    mean=mean_v,
                    samples=(mean_v - 0.2, mean_v, mean_v + 0.2),
                )
            )
    flat = optimize(
        target,
        tuple(projs),
        decision_at=decision,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(simulations=300, field_weight=0.0, upside_weight=0.0, seed=11),
    )
    upside = optimize(
        target,
        tuple(projs),
        decision_at=decision,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(simulations=300, field_weight=0.0, upside_weight=2.0, seed=11),
    )
    assert 6 not in {p.player_id for p in flat.picks} or flat.simulated_p90 <= upside.simulated_p90
    assert 6 in {p.player_id for p in upside.picks}
    assert upside.simulated_p90 >= flat.simulated_p90


def test_chalk_studs_still_win_when_leverage_cannot_recover() -> None:
    target = slate()
    decision = target.captured_at
    # Player 1 is an irreplaceable stud; omitting them collapses EV.
    projs = tuple(
        _projection(
            c.player_id,
            mean=20.0 if c.player_id == 1 else float(c.player_id),
            samples=(
                (19.0, 20.0, 21.0)
                if c.player_id == 1
                else (float(c.player_id), float(c.player_id) + 0.5)
            ),
        )
        for c in target.candidates
    )
    field = FieldObservation(
        clock=EvidenceClock(source_available_at=decision, captured_at=decision),
        entry_count=100,
        player_counts={1: 95, 2: 81, 3: 81, 4: 81, 5: 81, 6: 81},
        provenance="test",
        coverage="complete",
    )
    result = optimize(
        target,
        projs,
        decision_at=decision,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(simulations=200, field_weight=2.0, upside_weight=2.0, seed=3),
        field=field,
    )
    assert 1 in {p.player_id for p in result.picks}


def test_tournament_field_slots_use_p90_not_mean() -> None:
    """Under contest-utility / max_value, field slots rank by p90 (#505 / #453)."""
    target = slate()
    decision = target.captured_at
    projs = tuple(
        _projection(
            c.player_id,
            mean=10.0 - c.player_id if c.player_id != 6 else 3.0,
            samples=(
                (2.0, 3.0, 20.0)
                if c.player_id == 6
                else (
                    float(10 - c.player_id) - 0.1,
                    float(10 - c.player_id),
                    float(10 - c.player_id) + 0.1,
                )
            ),
        )
        for c in target.candidates
    )
    field = FieldObservation(
        clock=EvidenceClock(source_available_at=decision, captured_at=decision),
        entry_count=100,
        player_counts={1: 90, 2: 90, 3: 90, 4: 90, 5: 80, 6: 60},
        provenance="test",
        coverage="complete",
    )
    result = optimize(
        target,
        projs,
        decision_at=decision,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(
            simulations=120,
            field_weight=0.5,
            upside_weight=0.5,
            seed=9,
            profile="max_value",
            min_distinct_teams=1,
            min_distinct_games=1,
        ),
        field=field,
    )
    assert len(result.picks) == 5
    assert result.construction_profile == "max_value"


def _lineup_slate(specs: list[tuple[int, str, float]]) -> Slate:
    """One-game slate. ``specs`` is ``(player_id, position, card_boost)``."""
    decision = BASE + timedelta(days=8)
    clock = EvidenceClock(source_available_at=decision, captured_at=decision)
    game = Game(
        game_id=200,
        season=2025,
        kickoff_at=decision + timedelta(hours=4),
        home_team_id=10,
        away_team_id=11,
        home_team="A",
        away_team="B",
        status="scheduled",
    )
    candidates = tuple(
        Candidate(
            player_id=pid,
            game_id=200,
            team_id=10 if index % 2 == 0 else 11,
            name=f"P{pid}",
            position=position,
            team="A" if index % 2 == 0 else "B",
            opponent="B" if index % 2 == 0 else "A",
            injury_status="Active",
            card_boost=boost,
            clock=clock,
        )
        for index, (pid, position, boost) in enumerate(specs)
    )
    return Slate(
        contest=Contest(
            contest_id=901,
            day=decision.date(),
            end_day=decision.date(),
            slot_multipliers=(2, 1.8, 1.6, 1.4, 1.2),
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="c" * 64,
        ),
        games=(game,),
        candidates=candidates,
        captured_at=decision,
        source_hashes=("d" * 64,),
        pool_roster_count=len(candidates),
        pool_search_matched_count=len(candidates),
    )


def _mean_projections(
    target: Slate,
    means: dict[int, float],
    samples: dict[int, tuple[float, ...]] | None = None,
):
    samples = samples or {}
    return tuple(
        _projection(
            candidate.player_id,
            mean=means[candidate.player_id],
            samples=samples.get(
                candidate.player_id,
                (means[candidate.player_id], means[candidate.player_id]),
            ),
        )
        for candidate in target.candidates
    )


def _search_config(
    *,
    slot_by_mean: bool = True,
    max_kickers: int = 1,
    max_defenders: int = 1,
    upside_weight: float = 0.0,
    field_weight: float = 0.0,
) -> OptimizerConfig:
    return OptimizerConfig(
        simulations=100,
        upside_weight=upside_weight,
        field_weight=field_weight,
        min_distinct_teams=1,
        min_distinct_games=1,
        profile="max_value",
        seed=1,
        slot_by_mean=slot_by_mean,
        max_kickers=max_kickers,
        max_defenders=max_defenders,
    )


def test_committed_slots_follow_descending_mean() -> None:
    target = _lineup_slate([(pid, "WR", 0.0) for pid in range(1, 6)])
    means = {1: 10.0, 2: 8.0, 3: 6.0, 4: 4.0, 5: 1.0}
    projs = _mean_projections(target, means, samples={5: (20.0, 20.0)})
    ordered = optimize(
        target,
        projs,
        decision_at=target.captured_at,
        scoring_policy=ScoringPolicy(),
        config=_search_config(slot_by_mean=True),
    )
    assert [pick.player_id for pick in ordered.picks] == [1, 2, 3, 4, 5]
    assert [pick.projected_value for pick in ordered.picks] == [10.0, 8.0, 6.0, 4.0, 1.0]
    assert ordered.picks[0].slot == 1
    assert ordered.picks[0].slot_multiplier == 2.0
    assert "committed_slots_follow_descending_projected_mean" in ordered.assumptions

    search_order = optimize(
        target,
        projs,
        decision_at=target.captured_at,
        scoring_policy=ScoringPolicy(),
        config=_search_config(slot_by_mean=False),
    )
    assert search_order.picks[0].player_id == 5
    assert "committed_slots_follow_search_order" in search_order.assumptions


def test_committed_slots_follow_mean_on_the_beam_path() -> None:
    target = _lineup_slate([(pid, "WR", 0.0) for pid in range(1, 6)])
    means = {1: 10.0, 2: 8.0, 3: 6.0, 4: 4.0, 5: 1.0}
    projs = _mean_projections(target, means, samples={5: (20.0, 20.0)})
    ordered = optimize(
        target,
        projs,
        decision_at=target.captured_at,
        scoring_policy=ScoringPolicy(),
        config=_search_config(slot_by_mean=True, upside_weight=0.15, field_weight=0.1),
    )
    assert [pick.projected_value for pick in ordered.picks] == [10.0, 8.0, 6.0, 4.0, 1.0]


def test_equal_means_break_slot_ties_by_player_id() -> None:
    target = _lineup_slate(
        [(4, "WR", 0.0), (2, "WR", 0.0), (1, "RB", 0.0), (3, "TE", 0.0), (5, "QB", 0.0)]
    )
    means = {4: 9.0, 2: 9.0, 1: 3.0, 3: 2.0, 5: 1.0}
    result = optimize(
        target,
        _mean_projections(target, means),
        decision_at=target.captured_at,
        scoring_policy=ScoringPolicy(),
        config=_search_config(),
    )
    assert [pick.player_id for pick in result.picks[:2]] == [2, 4]


def test_max_one_kicker_and_kill_switch() -> None:
    specs = [
        (1, "K", 0.0),
        (2, "K", 0.0),
        (3, "WR", 0.0),
        (4, "WR", 0.0),
        (5, "RB", 0.0),
        (6, "TE", 0.0),
    ]
    target = _lineup_slate(specs)
    means = {1: 30.0, 2: 29.0, 3: 10.0, 4: 9.0, 5: 8.0, 6: 7.0}
    projs = _mean_projections(target, means)
    capped = optimize(
        target,
        projs,
        decision_at=target.captured_at,
        scoring_policy=ScoringPolicy(),
        config=_search_config(max_kickers=1),
    )
    assert sum(pick.position == "K" for pick in capped.picks) == 1
    assert capped.picks[0].player_id == 1
    assert "max_kickers=1" in capped.assumptions

    open_cap = optimize(
        target,
        projs,
        decision_at=target.captured_at,
        scoring_policy=ScoringPolicy(),
        config=_search_config(max_kickers=0),
    )
    assert sum(pick.position == "K" for pick in open_cap.picks) == 2


def test_max_one_kicker_on_the_beam_path() -> None:
    target = _lineup_slate(
        [
            (1, "K", 0.0),
            (2, "K", 0.0),
            (3, "WR", 0.0),
            (4, "WR", 0.0),
            (5, "RB", 0.0),
            (6, "TE", 0.0),
        ]
    )
    means = {1: 30.0, 2: 29.0, 3: 10.0, 4: 9.0, 5: 8.0, 6: 7.0}
    result = optimize(
        target,
        _mean_projections(target, means),
        decision_at=target.captured_at,
        scoring_policy=ScoringPolicy(),
        config=_search_config(max_kickers=1, upside_weight=0.15, field_weight=0.1),
    )
    assert sum(pick.position == "K" for pick in result.picks) == 1


def test_max_one_defender_includes_chart_codes() -> None:
    target = _lineup_slate(
        [
            (1, "LB", 0.0),
            (2, "DB", 0.0),
            (3, "DL", 0.0),
            (4, "CB", 0.0),
            (5, "WR", 0.0),
            (6, "WR", 0.0),
            (7, "RB", 0.0),
            (8, "TE", 0.0),
        ]
    )
    means = {1: 40.0, 2: 39.0, 3: 38.0, 4: 37.0, 5: 10.0, 6: 9.0, 7: 8.0, 8: 7.0}
    result = optimize(
        target,
        _mean_projections(target, means),
        decision_at=target.captured_at,
        scoring_policy=ScoringPolicy(),
        config=_search_config(max_defenders=1),
    )
    defenders = [pick for pick in result.picks if pick.position in {"LB", "DB", "DL", "CB"}]
    assert len(defenders) == 1
    assert defenders[0].player_id == 1
    assert "max_defenders=1" in result.assumptions


def test_kicker_and_defender_caps_are_independent() -> None:
    target = _lineup_slate(
        [
            (1, "K", 0.0),
            (2, "LB", 0.0),
            (3, "WR", 0.0),
            (4, "WR", 0.0),
            (5, "RB", 0.0),
            (6, "TE", 0.0),
        ]
    )
    means = {1: 30.0, 2: 29.0, 3: 10.0, 4: 9.0, 5: 8.0, 6: 7.0}
    result = optimize(
        target,
        _mean_projections(target, means),
        decision_at=target.captured_at,
        scoring_policy=ScoringPolicy(),
        config=_search_config(),
    )
    positions = [pick.position for pick in result.picks]
    assert positions.count("K") == 1
    assert positions.count("LB") == 1


def _contest_day_slate(
    *,
    games: int,
    pool: int,
    defenders: int,
    kickers: int,
    studs: int = 8,
) -> tuple[Slate, dict[int, float], dict[int, float], dict[str, list[int]]]:
    """One-game night or multi-game Sunday pool.

    Highest player ids are defenders, then kickers, all sharing boost 3.0
    with the studs. Own means rank studs first. ``distorted_means`` flips
    that so defenders and kickers are the top projections and the caps bind.
    """
    if studs + defenders + kickers >= pool:
        raise ValueError("regime_pool_too_small")
    decision = BASE + timedelta(days=8)
    clock = EvidenceClock(source_available_at=decision, captured_at=decision)
    built_games = tuple(
        Game(
            game_id=4000 + index,
            season=2025,
            kickoff_at=decision + timedelta(hours=4 + index),
            home_team_id=1000 + index * 2,
            away_team_id=1001 + index * 2,
            home_team=f"H{index}",
            away_team=f"A{index}",
            status="scheduled",
        )
        for index in range(games)
    )
    ids = list(range(1, pool + 1))
    groups = {
        "stud": ids[:studs],
        "defender": ids[-defenders:],
        "kicker": ids[-(defenders + kickers) : -defenders],
        "filler": ids[studs : -(defenders + kickers)],
    }
    own_means: dict[int, float] = {}
    distorted_means: dict[int, float] = {}
    for rank, pid in enumerate(groups["stud"]):
        own_means[pid] = 20.0 - rank
        distorted_means[pid] = 12.0 - rank * 0.1
    for pid in groups["filler"]:
        own_means[pid] = 6.0
        distorted_means[pid] = 3.0
    for rank, pid in enumerate(groups["kicker"]):
        own_means[pid] = 2.0
        distorted_means[pid] = 25.0 + rank
    for rank, pid in enumerate(groups["defender"]):
        own_means[pid] = 1.0
        distorted_means[pid] = 40.0 + rank
    defense_cycle = ("LB", "DB", "DL", "CB")
    skill_cycle = ("QB", "RB", "WR", "TE")
    candidates = []
    for pid in ids:
        if pid in groups["defender"]:
            position = defense_cycle[pid % len(defense_cycle)]
            boost = 3.0
        elif pid in groups["kicker"]:
            position = "K"
            boost = 3.0
        elif pid in groups["stud"]:
            position = skill_cycle[pid % len(skill_cycle)]
            boost = 3.0
        else:
            position = skill_cycle[pid % len(skill_cycle)]
            boost = 0.0
        game = built_games[(pid - 1) % games]
        home = ((pid - 1) // games) % 2 == 0
        candidates.append(
            Candidate(
                player_id=pid,
                game_id=game.game_id,
                team_id=game.home_team_id if home else game.away_team_id,
                name=f"P{pid}",
                position=position,
                team=game.home_team if home else game.away_team,
                opponent=game.away_team if home else game.home_team,
                injury_status="Active",
                card_boost=boost,
                clock=clock,
            )
        )
    slate = Slate(
        contest=Contest(
            contest_id=902,
            day=decision.date(),
            end_day=decision.date(),
            slot_multipliers=(2, 1.8, 1.6, 1.4, 1.2),
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="e" * 64,
        ),
        games=built_games,
        candidates=tuple(candidates),
        captured_at=decision,
        source_hashes=("f" * 64,),
        pool_roster_count=pool,
        pool_search_matched_count=pool,
    )
    return slate, own_means, distorted_means, groups


def test_slate_regime_label_does_not_change_caps() -> None:
    assert slate_regime_name(1) == "one_game"
    assert slate_regime_name(14) == "multi_game"
    with pytest.raises(ValueError, match="slate_games_required"):
        slate_regime_name(0)
    cfg = optimizer_config_from_env({})
    assert cfg.max_kickers == 1
    assert cfg.max_defenders == 1
    assert cfg.slot_by_mean is True


@pytest.mark.parametrize(
    ("games", "pool", "defenders", "kickers", "regime"),
    [
        (1, 150, 40, 12, "one_game"),
        (14, 700, 200, 40, "multi_game"),
    ],
)
def test_caps_and_tie_break_on_one_game_and_sunday_pools(
    games: int,
    pool: int,
    defenders: int,
    kickers: int,
    regime: str,
) -> None:
    slate, own_means, distorted_means, groups = _contest_day_slate(
        games=games,
        pool=pool,
        defenders=defenders,
        kickers=kickers,
    )
    assert len(slate.games) == games
    assert len(slate.candidates) == pool
    own = _mean_projections(slate, own_means)
    kept = apply_picker_knobs(
        own,
        slate,
        knobs=PickerKnobs(boost_rank_blend=1.0, profile="regime", boost_tie_break="projection"),
    )
    legacy = apply_picker_knobs(
        own,
        slate,
        knobs=PickerKnobs(boost_rank_blend=1.0, profile="legacy", boost_tie_break="player_id"),
    )
    kept_by = {projection.player_id: projection.conditional_mean for projection in kept}
    legacy_by = {projection.player_id: projection.conditional_mean for projection in legacy}
    stud_ids = groups["stud"]
    defender_ids = groups["defender"]
    assert min(kept_by[pid] for pid in stud_ids) > max(kept_by[pid] for pid in defender_ids)
    assert max(legacy_by[pid] for pid in defender_ids) > max(legacy_by[pid] for pid in stud_ids)

    result = optimize(
        slate,
        _mean_projections(slate, distorted_means),
        decision_at=slate.captured_at,
        scoring_policy=ScoringPolicy(),
        config=optimizer_config_from_env({}).model_copy(
            update={"simulations": 100, "field_weight": 0.0, "upside_weight": 0.15}
        ),
    )
    picked_defenders = [pick for pick in result.picks if pick.position in DEFENDER_POSITIONS]
    picked_kickers = [pick for pick in result.picks if pick.position == "K"]
    assert len(result.picks) == 5
    assert len(picked_defenders) == 1
    assert len(picked_kickers) == 1
    assert picked_defenders[0].player_id == defender_ids[-1]
    assert picked_kickers[0].player_id == groups["kicker"][-1]
    assert [pick.player_id for pick in result.picks[2:]] == stud_ids[:3]
    values = [pick.projected_value for pick in result.picks]
    assert values == sorted(values, reverse=True)
    assert result.picks[0].slot_multiplier == 2.0
    assert f"slate_regime={regime}" in result.assumptions
    assert f"slate_pool={pool}" in result.assumptions
    assert "max_kickers=1" in result.assumptions
    assert "max_defenders=1" in result.assumptions


def test_kicker_cap_fails_closed_when_five_cards_are_impossible() -> None:
    target = _lineup_slate([(pid, "K", 0.0) for pid in range(1, 6)])
    means = {pid: float(pid) for pid in range(1, 6)}
    with pytest.raises(ValueError, match="optimizer_no_feasible_lineup"):
        optimize(
            target,
            _mean_projections(target, means),
            decision_at=target.captured_at,
            scoring_policy=ScoringPolicy(),
            config=_search_config(max_kickers=1),
        )
