"""Anti-popularity contrarian adjustment + draft-popularity estimator."""

from __future__ import annotations

from wnba_oracle.picker.popularity import (
    ContrarianConfig,
    apply_contrarian_adjustment,
    estimate_draft_popularity,
    slate_labels_to_popularity,
)


def test_estimator_star_gets_higher_score_than_role_player() -> None:
    star = estimate_draft_popularity(season_ppg=24.0, team="NYL")
    role = estimate_draft_popularity(season_ppg=11.0, team="DAL")
    assert star > 4 * role


def test_estimator_big_market_amplifies() -> None:
    big = estimate_draft_popularity(season_ppg=18.0, team="LVA")
    small = estimate_draft_popularity(season_ppg=18.0, team="DAL")
    assert big > small * 1.25  # ~1.3x multiplier in the model


def test_estimator_small_slate_concentrates_drafts() -> None:
    small_slate = estimate_draft_popularity(season_ppg=18.0, n_games_on_slate=2)
    big_slate = estimate_draft_popularity(season_ppg=18.0, n_games_on_slate=10)
    assert small_slate > big_slate


def test_contrarian_disabled_returns_unchanged() -> None:
    preds = {1: 20.0, 2: 15.0}
    pop = {1: 4000.0, 2: 200.0}
    out = apply_contrarian_adjustment(preds, pop, ContrarianConfig(enabled=False))
    assert out == preds


def test_contrarian_penalizes_high_popularity_more() -> None:
    """The whole point: chalk should land lower than fade."""
    preds = {1: 20.0, 2: 20.0, 3: 20.0}
    pop = {1: 4000.0, 2: 1000.0, 3: 0.0}  # chalk, mid, fade
    out = apply_contrarian_adjustment(preds, pop)
    assert out[1] < out[2] < out[3]


def test_contrarian_unknown_player_no_penalty() -> None:
    preds = {1: 20.0, 2: 15.0}
    pop = {1: 4000.0}  # only player 1 has popularity data
    out = apply_contrarian_adjustment(preds, pop)
    assert out[1] < 20.0
    assert out[2] == 15.0  # unchanged


def test_slate_labels_to_popularity_rescales_to_estimator_anchor() -> None:
    drafts = {1: 100, 2: 200, 3: 300, 4: 400, 5: 500}
    out = slate_labels_to_popularity(drafts)
    # Median count is 300; scaled to anchor 2500 -> player 3 should be ~2500.
    assert 2400 < out[3] < 2600
    assert out[5] > out[3] > out[1]


def test_slate_labels_to_popularity_empty_returns_empty() -> None:
    assert slate_labels_to_popularity({}) == {}


def test_slate_labels_to_popularity_all_zero_returns_zero_dict() -> None:
    out = slate_labels_to_popularity({1: 0, 2: 0})
    assert out == {1: 0.0, 2: 0.0}
