from __future__ import annotations

import pandas as pd

from wnba_oracle.eval.identity_coverage import join_predictions_to_outcomes


def _alias(value: object) -> str:
    team = str(value or "").upper()
    return {"PHX": "PHO", "LV": "LVA"}.get(team, team)


def test_join_predictions_prefers_canonical_mapping_and_reports_unresolved_coverage() -> None:
    predictions = pd.DataFrame(
        [
            {
                "slate_date": "2026-07-01",
                "player_id": 1001,
                "display_name": "A. Wilson",
                "team": "LV",
            },
            {
                "slate_date": "2026-07-01",
                "player_id": 1002,
                "display_name": "B. Stewart",
                "team": "NYL",
            },
            {
                "slate_date": "2026-07-01",
                "player_id": 1003,
                "display_name": "Mystery Player",
                "team": "PHX",
            },
        ]
    )
    outcomes = pd.DataFrame(
        [
            {
                "game_date": "2026-07-01",
                "player_id": 9,
                "player_name": "A'ja Wilson",
                "team": "LVA",
                "min": 33.0,
                "pts": 24.0,
            },
            {
                "game_date": "2026-07-01",
                "player_id": 99,
                "player_name": "A. Wilson",
                "team": "LVA",
                "min": 1.0,
                "pts": 1.0,
            },
            {
                "game_date": "2026-07-01",
                "player_id": 12,
                "player_name": "Breanna Stewart",
                "team": "NYL",
                "min": 35.0,
                "pts": 20.0,
            },
        ]
    )
    canonical = pd.DataFrame(
        [
            {
                "real_sports_player_id": "1001",
                "wnba_player_id": 9,
                "provenance": "explicit_override",
            }
        ]
    )

    joined, report = join_predictions_to_outcomes(
        predictions=predictions,
        outcomes=outcomes,
        canonical_mapping=canonical,
        prediction_date_col="slate_date",
        prediction_player_id_col="player_id",
        prediction_name_col="display_name",
        prediction_team_col="team",
        outcome_date_col="game_date",
        outcome_player_id_col="player_id",
        outcome_name_col="player_name",
        outcome_team_col="team",
        fallback_team_alias=_alias,
    )

    assert float(joined.loc[joined["player_id"] == 1001, "pts"].iloc[0]) == 24.0
    assert float(joined.loc[joined["player_id"] == 1002, "pts"].iloc[0]) == 20.0
    assert joined.loc[joined["player_id"] == 1003, "pts"].isna().all()
    assert report.total_predictions == 3
    assert report.canonical_identity_resolved == 1
    assert report.canonical_outcome_matches == 1
    assert report.fallback_outcome_matches == 1
    assert report.unresolved_canonical_predictions == 2
    assert report.unresolved_canonical_rate == 2 / 3
