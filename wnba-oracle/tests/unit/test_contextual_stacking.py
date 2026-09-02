"""Contextual stacking policy, identity, and decision-trace tests."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

import numpy as np
import pytest

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import (
    OptimizeConfig,
    _Candidate,
    _candidate_pool_combinations,
    _ScanResult,
    _select_contextual_candidate,
    _StackContext,
    optimize_lineup,
)
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.sample import PlayerSamplingSpec
from wnba_oracle.picker.stacking import (
    LineupShape,
    describe_lineup,
    preference_for_slate,
    resolve_game_keys,
)


def _shape(*, games: int, teams: int, max_game: int, max_team: int) -> LineupShape:
    return LineupShape(
        game_count=games,
        team_count=teams,
        max_players_per_game=max_game,
        max_players_per_team=max_team,
        game_counts=(),
        team_counts=(),
    )


def _candidate(objective: float, shape: LineupShape, start: int) -> _Candidate:
    return _Candidate(
        objective=objective,
        indices=tuple(range(start, start + 5)),
        samples=np.full(10, objective),
        shape=shape,
    )


def _result(
    unrestricted: _Candidate,
    game: _Candidate | None,
    full: _Candidate | None,
) -> _ScanResult:
    return _ScanResult(unrestricted, game, full, 3, 0, 0, 0, 0)


def _context(n_games: int = 2) -> _StackContext:
    return _StackContext(
        game_key_by_player={},
        metadata_quality="provider_game_id",
        slate_game_count=n_games,
        slate_team_count=n_games * 2,
        preference=preference_for_slate(n_games, n_games * 2),
    )


def test_hard_policy_prefers_balanced_shape() -> None:
    unrestricted = _candidate(1.20, _shape(games=1, teams=2, max_game=5, max_team=3), 0)
    game = _candidate(1.195, _shape(games=2, teams=3, max_game=3, max_team=2), 5)
    full = _candidate(1.191, _shape(games=2, teams=4, max_game=3, max_team=2), 10)
    cfg = OptimizeConfig(contextual_stacking_enabled=True, contextual_stack_ev_margin=0.01)

    selected, decision = _select_contextual_candidate(
        _result(unrestricted, game, full), cfg, _context()
    )

    assert selected is full
    assert decision.reason == "hard_balance_selected"
    assert np.isclose(decision.objective_sacrifice, 0.009)


def test_clear_objective_advantage_allows_contextual_stack() -> None:
    unrestricted = _candidate(1.20, _shape(games=1, teams=2, max_game=5, max_team=3), 0)
    game = _candidate(1.18, _shape(games=2, teams=3, max_game=3, max_team=2), 5)
    full = _candidate(1.17, _shape(games=2, teams=4, max_game=3, max_team=2), 10)
    cfg = OptimizeConfig(contextual_stacking_enabled=True, contextual_stack_ev_margin=0.01)

    selected, decision = _select_contextual_candidate(
        _result(unrestricted, game, full), cfg, _context()
    )

    assert selected is full
    assert decision.reason == "hard_balance_selected"
    assert decision.objective_sacrifice == pytest.approx(0.03)


def test_dual_pool_enumeration_avoids_union_cross_product() -> None:
    unrestricted = frozenset(range(20))
    balanced = frozenset(range(20, 40))

    candidates = _candidate_pool_combinations(unrestricted, balanced)

    assert sum(1 for _combo, _legacy, _balance in candidates) == 31_008


def test_incomplete_metadata_is_explicit_and_does_not_force_balance() -> None:
    unrestricted = _candidate(1.20, _shape(games=1, teams=2, max_game=5, max_team=3), 0)
    context = _StackContext({}, "incomplete", None, 3, None)
    cfg = OptimizeConfig(contextual_stacking_enabled=True, contextual_stack_ev_margin=1.0)

    selected, decision = _select_contextual_candidate(
        _result(unrestricted, None, None), cfg, context
    )

    assert selected is unrestricted
    assert decision.reason == "metadata_incomplete"
    assert decision.slate_game_count is None


def _spec(
    player_id: int,
    team: str,
    opponent: str,
    game_id: str,
    pred: float = 3.0,
) -> tuple[PlayerSamplingSpec, FieldPlayerSpec]:
    sampling = PlayerSamplingSpec(
        player_id=player_id,
        team=team,
        opponent=opponent,
        game_id=game_id,
        mu=float(np.log(pred + 2.0)),
        sigma=0.05,
        boost=1.0,
        is_starter=True,
        blowout_prob=0.0,
        is_anchor=True,
    )
    field = FieldPlayerSpec(
        player_id=player_id,
        pred_real_score=pred,
        card_boost=1.0,
    )
    return sampling, field


def _slate(
    n_games: int,
    players_per_team: int = 3,
) -> tuple[list[PlayerSamplingSpec], list[FieldPlayerSpec]]:
    sampling: list[PlayerSamplingSpec] = []
    field: list[FieldPlayerSpec] = []
    player_id = 100
    for game in range(n_games):
        left = f"T{game * 2}"
        right = f"T{game * 2 + 1}"
        for team, opponent in ((left, right), (right, left)):
            for _ in range(players_per_team):
                sampling_spec, field_spec = _spec(
                    player_id,
                    team,
                    opponent,
                    f"G{game}",
                )
                sampling.append(sampling_spec)
                field.append(field_spec)
                player_id += 1
    return sampling, field


def test_two_game_flat_slate_prefers_both_games_and_all_teams() -> None:
    sampling, field = _slate(2)
    rec = optimize_lineup(
        sampling,
        field,
        default_curve_for_regime("top_20"),
        cfg=OptimizeConfig(
            top_n_filter=12,
            n_samples=80,
            n_field_lineups=10,
            seed=4,
            contextual_stacking_enabled=True,
            contextual_stack_ev_margin=10.0,
        ),
    )

    assert rec.stacking_decision is not None
    assert rec.stacking_decision.selected_game_count == 2
    assert rec.stacking_decision.selected_team_count == 4
    assert rec.stacking_decision.selected_max_players_per_game == 3


def test_five_game_slate_requires_exactly_one_player_from_each_game() -> None:
    sampling, field = _slate(5, players_per_team=2)
    rec = optimize_lineup(
        sampling,
        field,
        default_curve_for_regime("top_20"),
        cfg=OptimizeConfig(
            top_n_filter=10,
            n_samples=40,
            n_field_lineups=6,
            seed=7,
            contextual_stacking_enabled=False,
        ),
    )

    selected_games = {spec.game_id for spec in sampling if spec.player_id in set(rec.player_ids)}
    assert len(rec.player_ids) == 5
    assert selected_games == {"G0", "G1", "G2", "G3", "G4"}


def test_five_provider_games_with_inconsistent_teams_fail_closed() -> None:
    sampling, field = _slate(5, players_per_team=1)
    sampling[0] = replace(sampling[0], team="BROKEN")

    with pytest.raises(ValueError, match="five-game coverage metadata is inconsistent"):
        optimize_lineup(
            sampling,
            field,
            default_curve_for_regime("top_20"),
            cfg=OptimizeConfig(n_samples=20, n_field_lineups=5),
        )


def test_one_game_slate_remains_feasible_and_prefers_both_teams() -> None:
    sampling, field = _slate(1)
    rec = optimize_lineup(
        sampling,
        field,
        default_curve_for_regime("top_20"),
        cfg=OptimizeConfig(
            top_n_filter=6,
            n_samples=40,
            n_field_lineups=6,
            seed=3,
            contextual_stacking_enabled=True,
            contextual_stack_ev_margin=10.0,
        ),
    )

    assert rec.stacking_decision is not None
    assert rec.stacking_decision.selected_game_count == 1
    assert rec.stacking_decision.selected_team_count == 2
    assert rec.stacking_decision.effective_max_players_per_team == 5
    assert rec.stacking_decision.team_cap_reason == "dynamic_small_slate"


def test_large_flat_slate_limits_preferred_game_concentration_to_two() -> None:
    sampling, field = _slate(3)
    rec = optimize_lineup(
        sampling,
        field,
        default_curve_for_regime("top_20"),
        cfg=OptimizeConfig(
            top_n_filter=18,
            n_samples=80,
            n_field_lineups=10,
            seed=5,
            contextual_stacking_enabled=True,
            contextual_stack_ev_margin=10.0,
        ),
    )

    assert rec.stacking_decision is not None
    assert rec.stacking_decision.selected_game_count == 3
    assert rec.stacking_decision.selected_team_count >= 4
    assert rec.stacking_decision.selected_max_players_per_game == 2


def test_hard_policy_remains_active_when_legacy_toggle_is_disabled() -> None:
    sampling, field = _slate(3)
    rec = optimize_lineup(
        sampling,
        field,
        default_curve_for_regime("top_20"),
        cfg=OptimizeConfig(
            top_n_filter=18,
            n_samples=40,
            n_field_lineups=6,
            seed=5,
            contextual_stacking_enabled=False,
        ),
    )

    assert rec.stacking_decision is not None
    assert rec.stacking_decision.enabled is False
    assert rec.stacking_decision.selected_game_count is not None
    assert rec.stacking_decision.selected_game_count >= 2
    assert rec.stacking_decision.selected_max_players_per_game is not None
    assert rec.stacking_decision.selected_max_players_per_game <= 2
    assert rec.stacking_decision.selected_team_count >= 4


def test_contextual_decision_is_stable_under_input_reordering() -> None:
    sampling, field = _slate(2)
    cfg = OptimizeConfig(
        top_n_filter=12,
        n_samples=40,
        n_field_lineups=6,
        seed=6,
        contextual_stacking_enabled=True,
        contextual_stack_ev_margin=0.01,
    )
    curve = default_curve_for_regime("top_20")

    incumbent = optimize_lineup(sampling, field, curve, cfg=cfg)
    reordered = optimize_lineup(list(reversed(sampling)), list(reversed(field)), curve, cfg=cfg)

    assert reordered.player_ids == incumbent.player_ids
    assert reordered.stacking_decision == incumbent.stacking_decision


def test_contextual_mode_ignores_legacy_stack_bonus() -> None:
    sampling, field = _slate(2)
    with patch("wnba_oracle.picker.optimize._game_stack_pairs") as stack_pairs:
        rec = optimize_lineup(
            sampling,
            field,
            default_curve_for_regime("top_20"),
            cfg=OptimizeConfig(
                top_n_filter=12,
                n_samples=30,
                n_field_lineups=5,
                seed=7,
                game_stack_bonus=100.0,
                contextual_stacking_enabled=True,
            ),
        )

    stack_pairs.assert_not_called()
    assert rec.stacking_decision is not None
    assert rec.stacking_decision.legacy_stack_bonus_ignored is True


def test_top_n_filter_retains_balance_feasible_game_and_team_coverage() -> None:
    sampling, field = _slate(2)
    adjusted_sampling: list[PlayerSamplingSpec] = []
    adjusted_field: list[FieldPlayerSpec] = []
    for sampling_spec, field_spec in zip(sampling, field):
        pred = 10.0 if sampling_spec.game_id == "G0" else 1.0
        adjusted_sampling.append(replace(sampling_spec, mu=float(np.log(pred + 2.0))))
        adjusted_field.append(replace(field_spec, pred_real_score=pred))

    rec = optimize_lineup(
        adjusted_sampling,
        adjusted_field,
        default_curve_for_regime("top_20"),
        cfg=OptimizeConfig(
            top_n_filter=5,
            n_samples=30,
            n_field_lineups=5,
            seed=8,
            contextual_stacking_enabled=True,
            contextual_stack_ev_margin=10.0,
        ),
    )

    assert rec.stacking_decision is not None
    assert rec.stacking_decision.selected_game_count == 2
    assert rec.stacking_decision.selected_team_count == 4


def test_top_n_filter_preserves_concentrated_ev_override_candidate() -> None:
    sampling, field = _slate(2)
    adjusted_sampling: list[PlayerSamplingSpec] = []
    adjusted_field: list[FieldPlayerSpec] = []
    for sampling_spec, field_spec in zip(sampling, field):
        pred = 20.0 if sampling_spec.game_id == "G0" else 0.5
        adjusted_sampling.append(replace(sampling_spec, mu=float(np.log(pred + 2.0))))
        adjusted_field.append(replace(field_spec, pred_real_score=pred))

    rec = optimize_lineup(
        adjusted_sampling,
        adjusted_field,
        default_curve_for_regime("top_20"),
        cfg=OptimizeConfig(
            top_n_filter=5,
            n_samples=80,
            n_field_lineups=10,
            seed=9,
            contextual_stacking_enabled=True,
            contextual_stack_ev_margin=0.0,
        ),
    )

    assert rec.stacking_decision is not None
    assert rec.stacking_decision.reason == "hard_balance_selected"
    assert rec.stacking_decision.selected_game_count == 2
    assert rec.stacking_decision.best_game_balanced_objective is not None
    assert (
        rec.stacking_decision.best_unrestricted_objective
        > rec.stacking_decision.best_game_balanced_objective
    )


def test_provider_game_identity_survives_missing_opponent() -> None:
    sampling, _ = _slate(2, players_per_team=1)
    sampling = [replace(spec, opponent="") for spec in sampling]

    keys, quality, count = resolve_game_keys(sampling)

    assert quality == "provider_game_id"
    assert count == 2
    assert len(set(keys.values())) == 2


def test_fallback_requires_reciprocal_team_metadata() -> None:
    complete, _ = _slate(2, players_per_team=1)
    complete = [replace(spec, game_id="") for spec in complete]
    _, complete_quality, complete_count = resolve_game_keys(complete)
    broken = complete[:-1]
    _, broken_quality, broken_count = resolve_game_keys(broken)

    assert (complete_quality, complete_count) == ("team_opponent_fallback", 2)
    assert (broken_quality, broken_count) == ("incomplete", None)


def test_provider_rejects_team_mapped_to_multiple_game_ids() -> None:
    sampling = [
        _spec(1, "A", "B", "G1")[0],
        _spec(2, "B", "A", "G1")[0],
        _spec(3, "A", "B", "G2")[0],
        _spec(4, "B", "A", "G2")[0],
    ]

    keys, quality, count = resolve_game_keys(sampling)

    assert quality == "team_opponent_fallback"
    assert count == 1
    assert set(keys.values()) == {"teams:A|B"}


def test_provider_rejects_team_mapped_to_multiple_opponents() -> None:
    sampling = [
        _spec(1, "A", "B", "G1")[0],
        _spec(2, "A", "C", "G1")[0],
        _spec(3, "B", "A", "G1")[0],
    ]

    keys, quality, count = resolve_game_keys(sampling)

    assert quality == "incomplete"
    assert count is None
    assert set(keys.values()) == {""}


def test_fallback_rejects_team_mapped_to_multiple_opponents() -> None:
    sampling = [
        _spec(1, "A", "B", "")[0],
        _spec(2, "B", "A", "")[0],
        _spec(3, "A", "C", "")[0],
        _spec(4, "C", "A", "")[0],
    ]

    keys, quality, count = resolve_game_keys(sampling)

    assert quality == "incomplete"
    assert count is None
    assert set(keys.values()) == {""}


def test_describe_lineup_counts_games_and_teams() -> None:
    shape = describe_lineup(
        (0, 1, 2, 3, 4),
        ["A", "B", "C", "D", "A"],
        ["g1", "g1", "g2", "g2", "g1"],
    )
    assert shape.game_count == 2
    assert shape.team_count == 4
    assert shape.max_players_per_game == 3
    assert shape.max_players_per_team == 2
