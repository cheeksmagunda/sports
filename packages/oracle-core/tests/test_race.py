"""WIN/CLOSE race fitness helpers (#332, #339)."""

from __future__ import annotations

import pytest

from oracle_core.race import FitConfig, FitResult, rank_race, summarize_fitness


def test_fit_config_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="close_score_gap"):
        FitConfig(close_score_gap=-0.1)
    with pytest.raises(ValueError, match="close_score_pct"):
        FitConfig(close_score_pct=1.1)
    with pytest.raises(ValueError, match="min_races"):
        FitConfig(min_races=0)


def test_rank_race_marks_wins_ties_and_close_band() -> None:
    results = rank_race(
        {
            "alpha": 10.0,
            "bravo": 10.0,
            "charlie": 9.6,
            "delta": 8.9,
        },
        config=FitConfig(close_score_gap=0.5),
    )

    assert [result.result for result in results] == [
        FitResult.WIN,
        FitResult.WIN,
        FitResult.CLOSE,
        FitResult.OUT,
    ]


def test_rank_race_supports_lower_is_better_relative_close_band() -> None:
    results = rank_race(
        {
            "alpha": 100.0,
            "bravo": 104.0,
            "charlie": 109.0,
        },
        config=FitConfig(close_score_pct=0.05, higher_is_better=False),
    )

    assert [result.result for result in results] == [
        FitResult.WIN,
        FitResult.CLOSE,
        FitResult.OUT,
    ]


def test_summarize_fitness_uses_win_or_close_share_and_min_races() -> None:
    summaries = summarize_fitness(
        [
            {"alpha": 10.0, "bravo": 9.0, "charlie": 9.7},
            {"alpha": 8.0, "bravo": 8.0, "charlie": 7.6},
            {"bravo": 11.0, "charlie": 10.7},
        ],
        config=FitConfig(close_score_gap=0.5, min_races=3),
    )

    alpha = summaries["alpha"]
    assert alpha.races == 2
    assert alpha.wins == 2
    assert alpha.closes == 0
    assert alpha.win_or_close_share == 1.0
    assert alpha.eligible is False
    assert alpha.fitness == 0.0

    bravo = summaries["bravo"]
    assert bravo.races == 3
    assert bravo.wins == 2
    assert bravo.closes == 0
    assert bravo.losses == 1
    assert bravo.win_or_close_share == pytest.approx(2 / 3)
    assert bravo.eligible is True
    assert bravo.fitness == pytest.approx(2 / 3)

    charlie = summaries["charlie"]
    assert charlie.races == 3
    assert charlie.wins == 0
    assert charlie.closes == 3
    assert charlie.losses == 0
    assert charlie.win_or_close_share == 1.0
    assert charlie.fitness == 1.0
