from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from nfl_oracle.recommendations.model import (
    HistoricalPerformance,
    RatingModel,
    fit_model,
    predict,
)
from nfl_oracle.recommendations.optimizer import OptimizerConfig, ScoringPolicy, optimize
from nfl_oracle.recommendations.schema import EvidenceClock
from nfl_oracle.replay import production_backtest as pb
from nfl_oracle.replay.production_backtest import (
    LeakageError,
    assert_no_leakage,
    backtest_production_pipeline,
    build_slate,
    compact_projections,
    group_slates,
    hindsight_best,
    rows_before,
    summarize,
)

BASE = datetime(2024, 9, 8, 17, 0, tzinfo=UTC)
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
SKILL = {1: 9.0, 2: 1.0, 3: 4.0, 4: 2.5, 5: 7.0, 6: 0.5, 7: 3.0, 8: 6.0}


def _rows(games: int = 12, *, late_game: int | None = None) -> list[HistoricalPerformance]:
    rows = []
    for game in range(games):
        kickoff = BASE + timedelta(days=7 * game)
        delay = timedelta(days=9) if game == late_game else timedelta(hours=4)
        for player, skill in SKILL.items():
            team = 1 if player <= 4 else 2
            rows.append(
                HistoricalPerformance(
                    player_id=player,
                    game_id=1000 + game,
                    position="WR" if player % 2 else "RB",
                    kickoff_at=kickoff,
                    available_at=kickoff + delay,
                    captured_at=NOW - timedelta(days=1),
                    value=skill + 0.25 * ((player * game) % 3),
                    opportunity=float(player + game),
                    team_id=team,
                    opponent_team_id=3 - team,
                    did_not_play=player == 6 and game % 3 == 0,
                    context_features={"opp_def_value_allowed_prior": 1.0 + game % 2},
                    context_clock=EvidenceClock(source_available_at=NOW, captured_at=NOW),
                    context_evidence_mode="retrospective_reconstructed",
                )
            )
    return rows


def test_backtest_replays_production_fit_predict_optimize_and_reports_capture() -> None:
    results, excluded = backtest_production_pipeline(_rows(), now=NOW)
    # fit_model needs five distinct kickoffs and 30 rows: early slates skip visibly.
    assert excluded == {"fit:insufficient_training_history": 5}
    assert len(results) == 7
    for result in results:
        assert 0 < result.capture_ratio <= 1.0 + 1e-9
        assert len(result.predicted_player_ids) == 5
        assert result.selected_estimator == "ridge"  # context features wired (#212)
        assert result.candidate_count == len(
            [p for p in SKILL if not (p == 6 and (result.game_ids[0] - 1000) % 3 == 0)]
        )
    last = results[-1]
    assert last.hindsight_player_ids == (1, 5, 8, 3, 7)
    summary = summarize(results, excluded)
    assert summary.n_slates == 7
    assert summary.mean_capture_ratio is not None and summary.mean_capture_ratio > 0.5
    assert summary.excluded == excluded


def test_fitter_only_ever_sees_labels_final_before_the_slate_cutoff() -> None:
    rows = _rows(late_game=7)  # game 1007's label finalizes after game 1008 kicks off
    seen: list[frozenset[int]] = []

    def spy(train: Sequence[HistoricalPerformance], trained_at: datetime) -> RatingModel:
        seen.append(frozenset(r.game_id for r in train))
        return fit_model(train, trained_at=trained_at)

    backtest_production_pipeline(rows, now=NOW, fitter=spy)
    # One retrain per slate, in cutoff order: seen[i] trains the slate for game 1000+i.
    assert len(seen) == 12
    assert seen[0] == frozenset()
    assert 1006 in seen[8] and 1007 not in seen[8]
    assert 1007 in seen[9]
    assert all(1000 + i not in games for i, games in enumerate(seen))


def test_leakage_guard_rejects_future_and_same_slate_labels() -> None:
    rows = _rows(games=3)
    cutoff = rows[8].kickoff_at  # game 1001
    with pytest.raises(LeakageError, match="future_label_in_training"):
        assert_no_leakage(rows, cutoff=cutoff, slate_game_ids=())
    with pytest.raises(LeakageError, match="slate_game_in_training"):
        assert_no_leakage(rows[:8], cutoff=cutoff, slate_game_ids=(1000,))
    assert_no_leakage(rows_before(rows, cutoff=cutoff), cutoff=cutoff, slate_game_ids=(1001,))


def test_backtest_fails_closed_when_walk_forward_filter_is_bypassed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def leaky_rows_before(
        rows: Sequence[HistoricalPerformance], **_kwargs: object
    ) -> tuple[HistoricalPerformance, ...]:
        return tuple(rows)

    monkeypatch.setattr(pb, "rows_before", leaky_rows_before)
    with pytest.raises(LeakageError):
        backtest_production_pipeline(_rows(), now=NOW)


def test_compact_projections_select_the_same_lineup_as_full_samples() -> None:
    rows = _rows()
    target = [r for r in rows if r.game_id == 1011]
    history = rows_before(rows, cutoff=target[0].kickoff_at)
    model = fit_model(history, trained_at=NOW)
    slate = build_slate(target, now=NOW)
    projections = predict(slate, model, history, decision_at=NOW)
    config = OptimizerConfig(simulations=100)
    full = optimize(
        slate, projections, decision_at=NOW, scoring_policy=ScoringPolicy(), config=config
    )
    compact = optimize(
        slate,
        compact_projections(projections),
        decision_at=NOW,
        scoring_policy=ScoringPolicy(),
        config=config,
    )
    assert [p.player_id for p in full.picks] == [p.player_id for p in compact.picks]
    assert full.total_value == pytest.approx(compact.total_value)


def test_hindsight_best_and_day_grouping() -> None:
    ids, score = hindsight_best(
        {1: 1.0, 2: 5.0, 3: 3.0, 4: 2.0, 5: 4.0, 6: 0.5}, pb.SLOT_MULTIPLIERS
    )
    assert ids == (2, 5, 3, 4, 1)
    assert score == pytest.approx(5 * 2.0 + 4 * 1.8 + 3 * 1.6 + 2 * 1.4 + 1 * 1.2)
    rows = _rows(games=2)
    shifted = [
        r.model_copy(
            update={
                "game_id": 2000,
                "kickoff_at": r.kickoff_at + timedelta(hours=3),
                "available_at": r.available_at + timedelta(hours=3),
                "team_id": (r.team_id or 0) + 10,
                "opponent_team_id": (r.opponent_team_id or 0) + 10,
                "player_id": r.player_id + 100,
            }
        )
        for r in rows
        if r.game_id == 1000
    ]
    specs = group_slates([*rows, *shifted], "day")
    assert [spec.game_ids for spec in specs] == [(1000, 2000), (1001,)]
    slate = build_slate(specs[0].rows, now=NOW)
    assert len(slate.games) == 2
    assert all(not c.player_id == 6 for c in slate.candidates)  # game 1000 DNP excluded
