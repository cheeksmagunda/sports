"""Unit tests for observation-only research readiness score."""

from __future__ import annotations

from nfl_oracle.strategy.readiness_score import (
    band_for_score,
    compute_research_readiness_score,
    readiness_score_from_summaries,
)


def test_band_for_score_thresholds() -> None:
    assert band_for_score(0) == "thin"
    assert band_for_score(39.9) == "thin"
    assert band_for_score(40) == "usable_offline"
    assert band_for_score(70) == "dense_offline"
    assert band_for_score(90) == "research_strong"


def test_empty_inputs_are_thin_and_deny_entry() -> None:
    report = compute_research_readiness_score()
    assert report.contest_entry is False
    assert report.observation_only is True
    assert report.score == 0.0
    assert report.band == "thin"
    body = report.to_json_obj()
    assert body["contest_entry"] is False
    assert body["entry_authorized"] is False
    assert body["policy"] == "deny_by_default_entry_gates"
    assert body["max_score"] == 100.0
    assert len(body["components"]) == 7


def test_full_offline_targets_score_high_without_auth() -> None:
    report = compute_research_readiness_score(
        seed_game_count=70,
        known_ratio=0.85,
        schedule_game_count=4000,
        continuous_regular_season_count=16,
        identity_n=100,
        identity_complete_ratio=0.85,
        live_ok_feature_count=12,
        unknown_provider_rule_count=7,
        offline_rule_note_count=7,
        auth_usable=False,
    )
    # Auth weight 10 missing → score around 90
    assert report.score == 90.0
    assert report.band == "research_strong"
    assert report.contest_entry is False
    auth = next(c for c in report.components if c.key == "realsports_auth")
    assert auth.unit_score == 0.0


def test_auth_usable_reaches_100() -> None:
    report = compute_research_readiness_score(
        seed_game_count=70,
        known_ratio=0.85,
        schedule_game_count=4000,
        continuous_regular_season_count=16,
        identity_n=100,
        identity_complete_ratio=0.85,
        live_ok_feature_count=12,
        unknown_provider_rule_count=7,
        offline_rule_note_count=7,
        auth_usable=True,
    )
    assert report.score == 100.0
    assert report.band == "research_strong"


def test_partial_provider_notes_scale() -> None:
    half = compute_research_readiness_score(
        unknown_provider_rule_count=7,
        offline_rule_note_count=0,
    )
    full_notes = compute_research_readiness_score(
        unknown_provider_rule_count=7,
        offline_rule_note_count=7,
    )
    rules_half = next(c for c in half.components if c.key == "provider_rules_offline")
    rules_full = next(c for c in full_notes.components if c.key == "provider_rules_offline")
    assert rules_half.unit_score == 0.0
    assert rules_full.unit_score == 1.0


def test_readiness_score_from_summaries_maps_payloads() -> None:
    data = {
        "catalog": {"seed_game_count": 70},
        "density": {"known_ratio": 12 / 14, "catalog_seed_game_count": 70},
        "schedule": {
            "continuous_regular_season_count": 8,
            "density": {"game_count": 2000},
        },
        "identity": {
            "n_identities": 100,
            "density": {"complete_ratio": 0.9},
        },
    }
    report = readiness_score_from_summaries(
        data_summary=data,
        live_ok_feature_count=10,
        unknown_provider_rule_count=7,
        offline_rule_note_count=7,
        auth_usable=False,
    )
    assert report.contest_entry is False
    assert report.score > 40.0
    assert report.band in {"usable_offline", "dense_offline", "research_strong"}
