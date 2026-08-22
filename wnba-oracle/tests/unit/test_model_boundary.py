"""Versioned policy and input fingerprints at the infrastructure/model seam."""

from __future__ import annotations

import datetime as dt
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from wnba_oracle.common.settings import Settings
from wnba_oracle.modeling.policy import ModelPolicy
from wnba_oracle.modeling.prediction import PlayerPredictions
from wnba_oracle.modeling.prediction import materialize_specs as materialize_model_specs
from wnba_oracle.modeling.prediction import predict_players as predict_model_players
from wnba_oracle.modeling.provenance import (
    ScoringProvenance,
    canonical_enrichment_payload,
    enrichment_sequence_payload,
)
from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.sample import PlayerSamplingSpec
from wnba_oracle.scheduler import job2, job2_specs
from wnba_oracle.scheduler.job2 import MODEL_POLICY_SETTING_FIELDS, build_model_policy


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "model_artifact_sha": "a" * 64,
        "payout_regime": "top_20",
        "optimizer_top_n_filter": 20,
        "optimizer_n_samples": 1000,
        "optimizer_n_field_lineups": 500,
        "optimizer_max_per_team": 2,
        "optimizer_dynamic_team_cap": True,
        "sampling_score_offset": 2.0,
        "starter_signal_enabled": True,
        "starter_signal_use_expected": True,
        "starter_unknown_fade": 0.75,
        "game_script_minutes_enabled": True,
        "availability_model_enabled": True,
        "minutes_model_enabled": True,
        "database_url": "postgresql://infra-only-a",
    }
    values.update(overrides)
    return Settings.model_construct(**values)


def _rows() -> list[dict]:
    return [
        {
            "real_sports_player_id": "22",
            "name": "Player B",
            "team": "NYL",
            "opponent": "IND",
            "position": "F",
            "card_boost": 1.5,
            "features_json": '{"recent_minutes":28.0,"is_starter":1}',
        },
        {
            "real_sports_player_id": 11,
            "name": "Player A",
            "team": "IND",
            "opponent": "NYL",
            "position": "G",
            "card_boost": 0.5,
            "features_json": {"is_starter": 0, "recent_minutes": 25.0},
        },
    ]


def test_model_policy_fingerprint_ignores_infrastructure_only_settings() -> None:
    first = build_model_policy(_settings(database_url="postgresql://one"))
    second = build_model_policy(_settings(database_url="postgresql://two"))

    assert first == second
    assert first.sha256 == second.sha256


def test_model_policy_setting_inventory_covers_current_settings_surface() -> None:
    model_prefixes = (
        "boost_tail_",
        "ceiling_sigma_",
        "contrarian_",
        "field_same_",
        "optimizer_",
        "picker_boost_",
        "picker_floor_",
        "starter_",
    )
    model_fields = {
        name
        for name in Settings.model_fields
        if name.startswith(model_prefixes)
        or name
        in {
            "availability_model_enabled",
            "caveat_is_skip",
            "field_measured_ownership_enabled",
            "game_script_minutes_enabled",
            "lineup_anchor_floor",
            "minutes_model_enabled",
            "model_artifact_sha",
            "never_skip",
            "payout_regime",
            "prop_signal_scale",
            "sampling_score_offset",
        }
    }

    assert model_fields == MODEL_POLICY_SETTING_FIELDS
    assert build_model_policy(Settings.model_construct()).optimizer.ceiling_tilt_slots is True


def test_model_policy_fingerprint_changes_with_model_setting() -> None:
    incumbent = build_model_policy(_settings(starter_unknown_fade=0.75))
    challenger = build_model_policy(_settings(starter_unknown_fade=0.80))

    assert incumbent.sha256 != challenger.sha256


def test_model_policy_round_trips_through_persisted_payload() -> None:
    policy = build_model_policy(_settings())

    assert ModelPolicy.from_payload(policy.to_payload()) == policy
    with pytest.raises(ValueError, match="schema_version"):
        ModelPolicy.from_payload({**policy.to_payload(), "schema_version": 999})


def test_invalid_model_policy_returns_a_structured_job_failure() -> None:
    with patch.object(job2, "get_settings", return_value=_settings(optimizer_n_samples=0)):
        result = job2.run("2026-08-22", dry_run=True)

    assert result.reason == "model_policy_invalid"
    assert result.exit_code == 1


def test_legacy_prediction_module_preserves_settings_keyword_contract() -> None:
    settings = _settings()
    policy = build_model_policy(settings)
    direct = predict_model_players(
        [],
        policy=policy,
        art=None,
        head_predictions={},
        player_history=None,
        bonus={},
    )
    legacy = job2_specs.predict_players(
        [],
        settings=settings,
        art=None,
        head_predictions={},
        player_history=None,
        bonus={},
    )

    assert legacy == direct == PlayerPredictions()
    assert job2_specs.materialize_specs(
        {},
        preds=legacy,
        settings=settings,
        measured_drafts={},
        label_names={},
        K=policy.optimizer.score_offset,
        volatility={},
    ) == materialize_model_specs(
        {},
        preds=direct,
        policy=policy,
        measured_drafts={},
        label_names={},
        K=policy.optimizer.score_offset,
        volatility={},
    )


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"optimizer_n_samples": 0}, "n_samples must be positive"),
        ({"sampling_score_offset": -1.0}, "score_offset must be positive"),
        ({"starter_minutes_lift_weight": 2.0}, "lift_weight must be between"),
    ],
)
def test_model_policy_rejects_invalid_math_configuration(
    override: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        build_model_policy(_settings(**override))


def test_canonical_enrichment_fingerprint_ignores_adapter_order_and_json_format() -> None:
    rows = _rows()
    reordered = [dict(rows[1]), dict(rows[0])]
    reordered[1]["features_json"] = json.dumps(
        {"is_starter": 1, "recent_minutes": 28.0},
        indent=2,
    )

    assert canonical_enrichment_payload(rows) == canonical_enrichment_payload(reordered)
    assert enrichment_sequence_payload(rows) != enrichment_sequence_payload(reordered)


def test_capture_timestamp_is_not_part_of_the_model_input_fingerprint() -> None:
    rows = _rows()
    timestamped = [dict(row) for row in rows]
    timestamped[0]["captured_at"] = dt.datetime(2026, 8, 22, 20, 0, tzinfo=dt.UTC)
    timestamped[1]["captured_at"] = "2026-08-22T20:05:00+00:00"

    assert canonical_enrichment_payload(rows) == canonical_enrichment_payload(timestamped)
    assert enrichment_sequence_payload(rows) == enrichment_sequence_payload(timestamped)


def test_job2_assurance_failure_is_value_free_and_does_not_raise() -> None:
    secret_message = "postgresql://user:password@example/token-value"
    with patch(
        "wnba_oracle.assurance.source_quality.build_source_assurance",
        side_effect=RuntimeError(secret_message),
    ):
        payload = job2._safe_source_assurance(
            _rows(),
            assessed_at=dt.datetime(2026, 8, 22, 22, 20, tzinfo=dt.UTC),
            decision_input_sha256="a" * 64,
            decision_input_canonical_sha256="c" * 64,
            finding_triggers=[],
            assessment_error_type=None,
        )

    serialized = json.dumps(payload, sort_keys=True)
    assert payload["assessment_status"] == "unknown"
    assert payload["error"] == {"type": "RuntimeError"}
    assert "password" not in serialized
    assert "token-value" not in serialized


@pytest.mark.parametrize(
    ("malformed_findings", "error_type"),
    [
        (None, "TypeError"),
        ([object()], "AttributeError"),
        ([SimpleNamespace(trigger=17)], "TypeError"),
    ],
)
def test_serving_schema_contract_drift_cannot_block_job2(
    malformed_findings: object, error_type: str
) -> None:
    with patch(
        "wnba_oracle.features.serving_schema.validate_enrichment",
        return_value=malformed_findings,
    ):
        triggers, assessment_error_type = job2._record_serving_schema_findings(
            "2026-08-22",
            _rows(),
        )

    assert triggers == []
    assert assessment_error_type == error_type


@pytest.mark.parametrize(
    ("malformed_payload", "error_type"),
    [
        (
            {
                "decision_input_sha256": "a" * 64,
                "decision_input_canonical_sha256": "c" * 64,
                "bad": object(),
            },
            "TypeError",
        ),
        (
            {
                "decision_input_sha256": "b" * 64,
                "decision_input_canonical_sha256": "c" * 64,
            },
            "ValueError",
        ),
        (
            {
                "decision_input_sha256": "a" * 64,
                "decision_input_canonical_sha256": "d" * 64,
            },
            "ValueError",
        ),
    ],
)
def test_job2_rejects_malformed_assurance_without_blocking_freeze(
    malformed_payload: dict[str, object], error_type: str
) -> None:
    with patch(
        "wnba_oracle.assurance.source_quality.build_source_assurance",
        return_value=malformed_payload,
    ):
        payload = job2._safe_source_assurance(
            _rows(),
            assessed_at=dt.datetime(2026, 8, 22, 22, 20, tzinfo=dt.UTC),
            decision_input_sha256="a" * 64,
            decision_input_canonical_sha256="c" * 64,
            finding_triggers=[],
            assessment_error_type=None,
        )

    assert payload["assessment_status"] == "unknown"
    assert payload["decision_input_sha256"] == "a" * 64
    assert payload["decision_input_canonical_sha256"] == "c" * 64
    assert payload["error"] == {"type": error_type}


def test_scoring_provenance_records_policy_and_input_hashes_without_activating_sort() -> None:
    policy = build_model_policy(_settings())
    sampling = [
        PlayerSamplingSpec(
            player_id=11,
            team="IND",
            opponent="NYL",
            mu=1.0,
            sigma=0.2,
            boost=0.5,
        )
    ]
    field = [FieldPlayerSpec(player_id=11, pred_real_score=3.0, card_boost=0.5)]
    curve = default_curve_for_regime("top_20")
    provenance = ScoringProvenance.capture(
        model_policy=policy,
        enrichment=_rows(),
        sampling_specs=sampling,
        field_specs=field,
        payout_curve=curve,
        artifact_loaded=True,
        artifact_feature_module_sha="artifact-feature-sha",
        serving_feature_module_sha="serving-feature-sha",
    )
    payload = provenance.to_payload()

    assert payload["model_engine_version"] == "1"
    assert payload["model_policy_sha256"] == policy.sha256
    assert payload["model_policy"]["schema_version"] == 1
    assert len(payload["enrichment_sha256"]) == 64
    assert len(payload["enrichment_sequence_sha256"]) == 64
    assert payload["enrichment_rows"] == 2
    assert len(payload["optimizer_inputs_sha256"]) == 64
    assert payload["optimizer_players"] == 1
    assert payload["optimizer_inputs"]["sampling_specs"][0]["player_id"] == 11
    assert payload["artifact_loaded"] is True
    assert payload["artifact_feature_module_match"] is False
    assert payload["canonical_order_active"] is False

    changed_curve = default_curve_for_regime("top_1")
    changed = ScoringProvenance.capture(
        model_policy=policy,
        enrichment=_rows(),
        sampling_specs=sampling,
        field_specs=field,
        payout_curve=changed_curve,
    )
    assert changed.optimizer_inputs_sha256 != provenance.optimizer_inputs_sha256
