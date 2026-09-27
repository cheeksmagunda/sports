"""Priority RS leaf aliases → NFL own-model ridge context (#523)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nfl_oracle.baselines.value_model import CONTEXT_FEATURE_NAMES, FeatureDrivenValueModel
from nfl_oracle.features.live import REQUIRED_LIVE_OK_CONTEXT_FEATURES
from nfl_oracle.features.own_model_map import classify_feature
from nfl_oracle.features.rs_aliases import (
    LEAKAGE_BLOCKED_SAME_SLATE,
    REQUIRED_RS_POOL_CONTEXT_FEATURES,
    RS_FEATURE_ALIASES,
    extract_box_participation,
    extract_draft_stats_row,
    extract_moneyline_priors,
    extract_pool_card_features,
    extract_season_averages,
    hash_categorical,
)
from nfl_oracle.labels.schema import ValueLabel
from nfl_oracle.recommendations.model import HistoricalPerformance, fit_model
from nfl_oracle.recommendations.schema import Candidate, EvidenceClock, Game


def test_priority_aliases_table() -> None:
    assert RS_FEATURE_ALIASES["overallRank"] == "overall_rank"
    assert RS_FEATURE_ALIASES["baseBoostedValue"] == "base_boosted_value"
    assert RS_FEATURE_ALIASES["injuryBodyPart"] == "injury_body_part"
    assert RS_FEATURE_ALIASES["didNotPlay"] == "did_not_play"
    assert RS_FEATURE_ALIASES["lastTenWins"] == "last_ten_wins"
    assert "base_boosted_value" in LEAKAGE_BLOCKED_SAME_SLATE
    assert "minutes" in LEAKAGE_BLOCKED_SAME_SLATE


def test_pool_card_and_moneyline_extractors() -> None:
    feats = extract_pool_card_features({"overallRank": 12, "injuryBodyPart": "Ankle"})
    assert feats["overall_rank"] == 12.0
    assert feats["injury_body_part_available"] == 1.0
    bucket, _ = hash_categorical("Ankle")
    assert feats["injury_body_part_hash"] == bucket
    ml = extract_moneyline_priors(home_moneyline=-150, away_moneyline=130, is_home=True)
    assert ml["team_moneyline"] == -150.0
    assert ml["opponent_moneyline"] == 130.0
    assert ml["moneyline_available"] == 1.0


def test_same_slate_box_and_draft_stats_blocked() -> None:
    assert (
        extract_box_participation(
            {"didNotPlay": False, "started": True, "minutes": 28}, mode="live_ok"
        )
        == {}
    )
    prior = extract_box_participation(
        {"didNotPlay": False, "started": True, "minutes": 28}, mode="historical_prior"
    )
    assert prior == {
        "prior_did_not_play": 0.0,
        "prior_started": 1.0,
        "prior_minutes": 28.0,
    }
    assert (
        extract_draft_stats_row({"baseBoostedValue": 9.5, "score": 40, "rank": 2}, mode="live_ok")
        == {}
    )
    prior_ds = extract_draft_stats_row(
        {"baseBoostedValue": 9.5, "score": 40, "rank": 2}, mode="historical_prior"
    )
    assert prior_ds["prior_base_boosted_value"] == 9.5
    assert prior_ds["prior_draft_stats_score"] == 40.0
    assert prior_ds["prior_draft_stats_rank"] == 2.0


def test_season_averages_flatten() -> None:
    assert extract_season_averages({}) == {}
    assert extract_season_averages({"pts": 18.2, "reb": 4.1, "note": "x"}) == {
        "season_avg_pts": 18.2,
        "season_avg_reb": 4.1,
    }


def test_required_rs_pool_force_included_on_ridge() -> None:
    for key in REQUIRED_RS_POOL_CONTEXT_FEATURES:
        assert key in REQUIRED_LIVE_OK_CONTEXT_FEATURES
        assert key in CONTEXT_FEATURE_NAMES
    assert classify_feature("overall_rank") == "context_required"
    assert classify_feature("base_boosted_value") == "leakage_blocked"
    assert classify_feature("draft_stats_score") == "leakage_blocked"


def test_feature_ridge_consumes_rs_pool_context() -> None:
    train = [
        ValueLabel(
            player_id=1,
            game_id=1,
            season=2022,
            position="WR",
            value=8.0,
            team_id=1,
            context_features={"overall_rank": 5.0, "team_moneyline": -120.0},
        ),
        ValueLabel(
            player_id=2,
            game_id=2,
            season=2022,
            position="RB",
            value=6.0,
            team_id=1,
            context_features={"overall_rank": 40.0, "last_ten_wins": 7.0},
        ),
        ValueLabel(
            player_id=1,
            game_id=3,
            season=2023,
            position="WR",
            value=9.0,
            team_id=1,
            context_features={"overall_rank": 4.0, "prior_minutes": 30.0},
        ),
        ValueLabel(
            player_id=2,
            game_id=4,
            season=2023,
            position="RB",
            value=5.5,
            team_id=1,
            context_features={"overall_rank": 50.0},
        ),
    ]
    model = FeatureDrivenValueModel(alpha=1.0).fit(train)
    assert "overall_rank" in model.context_feature_names
    matrix = model.design_matrix(train)
    idx = model.context_feature_names.index("overall_rank")
    core = len(model.feature_names)
    assert matrix[0][core + 2 * idx] == 5.0


def test_candidate_and_game_carry_rs_fields() -> None:
    clock = EvidenceClock(
        source_available_at=datetime(2025, 9, 7, 12, tzinfo=UTC),
        captured_at=datetime(2025, 9, 7, 12, tzinfo=UTC),
    )
    game = Game(
        game_id=1,
        season=2025,
        kickoff_at=datetime(2025, 9, 7, 17, tzinfo=UTC),
        home_team_id=10,
        away_team_id=20,
        home_team="KC",
        away_team="BAL",
        status="scheduled",
        home_moneyline=-200.0,
        away_moneyline=170.0,
        home_last_ten_wins=8.0,
    )
    cand = Candidate(
        player_id=99,
        game_id=1,
        team_id=10,
        name="Test Player",
        position="WR",
        team="KC",
        opponent="BAL",
        injury_status="Questionable",
        card_boost=1.0,
        clock=clock,
        overall_rank=11.0,
        injury_body_part="Calf",
    )
    assert cand.overall_rank == 11.0
    assert game.home_moneyline == -200.0


def test_production_fit_force_includes_rs_pool_keys() -> None:
    kick = datetime(2025, 9, 7, 17, tzinfo=UTC)
    rows = []
    for game in range(6):
        for player in range(1, 7):
            rows.append(
                HistoricalPerformance(
                    player_id=player,
                    game_id=100 + game,
                    position="WR",
                    role="receiving",
                    kickoff_at=kick + timedelta(days=game),
                    available_at=kick + timedelta(days=game, hours=2),
                    captured_at=kick + timedelta(days=game, hours=3),
                    value=float(player + game),
                    opportunity=float(player + game),
                    did_not_play=False,
                    context_features={},
                    context_clock=None,
                )
            )
    model = fit_model(rows, trained_at=kick + timedelta(days=10))
    for key in ("overall_rank", "team_moneyline", "last_ten_wins", "prior_minutes"):
        assert key in model.context_feature_names
