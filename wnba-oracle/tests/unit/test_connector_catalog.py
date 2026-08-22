"""Stable, value-free connector catalog contract."""

from __future__ import annotations

import json
import re
from dataclasses import replace

from wnba_oracle.assurance.connectors import (
    CONNECTOR_CATALOG_SCHEMA_VERSION,
    CONNECTOR_CATALOG_SHA256,
    CONNECTORS,
    DECISION_INPUT_CONNECTOR_CATALOG_SHA256,
    DECISION_INPUT_CONNECTOR_IDS,
    connector_catalog_payload,
    decision_input_connector_catalog_payload,
)


def test_connector_ids_are_unique_and_catalog_is_canonical() -> None:
    connector_ids = [connector.connector_id for connector in CONNECTORS]
    assert len(connector_ids) == len(set(connector_ids))

    payload = connector_catalog_payload()
    serialized_ids = [row["connector_id"] for row in payload["connectors"]]
    assert payload["schema_version"] == CONNECTOR_CATALOG_SCHEMA_VERSION == 1
    assert serialized_ids == sorted(connector_ids)
    assert re.fullmatch(r"[0-9a-f]{64}", CONNECTOR_CATALOG_SHA256)
    assert re.fullmatch(r"[0-9a-f]{64}", DECISION_INPUT_CONNECTOR_CATALOG_SHA256)
    json.dumps(payload, sort_keys=True, allow_nan=False)
    assert all(connector.criticality for connector in CONNECTORS)


def test_catalog_contains_every_freeze_observation_connector() -> None:
    connector_ids = set(DECISION_INPUT_CONNECTOR_IDS)
    assert {
        "postgres",
        "identity_override_file",
        "payout_archive",
        "realsports",
        "rotowire",
        "the_odds_api",
        "wnba_stats",
    } <= connector_ids
    assert "model_artifact" in connector_ids
    assert connector_ids == {
        connector.connector_id for connector in CONNECTORS if connector.affects_decision
    }


def test_non_decision_connector_changes_do_not_change_decision_input_catalog() -> None:
    mutated = tuple(
        replace(connector, failure_semantics="changed_non_decision_contract")
        if connector.connector_id in {"frontend", "github_actions"}
        else connector
        for connector in CONNECTORS
    )

    assert connector_catalog_payload(mutated) != connector_catalog_payload()
    assert decision_input_connector_catalog_payload(mutated) == (
        decision_input_connector_catalog_payload()
    )


def test_catalog_declares_credential_names_without_values_or_endpoints() -> None:
    serialized = json.dumps(connector_catalog_payload(), sort_keys=True)
    assert "://" not in serialized
    assert "railway.app" not in serialized
    assert "web.realapp.com" not in serialized

    for connector in CONNECTORS:
        for variable_name in (
            *connector.credential_env_vars,
            *connector.configuration_env_vars,
        ):
            assert re.fullmatch(r"[A-Z][A-Z0-9_]+", variable_name)
            assert "=" not in variable_name
    artifact = next(item for item in CONNECTORS if item.connector_id == "model_artifact")
    assert artifact.criticality == "required"
    assert artifact.credential_class == "none"
    assert artifact.credential_env_vars == ()
    assert "WNBA_ORACLE_MODEL_ARTIFACT_SHA" in artifact.configuration_env_vars


def test_postgres_catalog_covers_runtime_backup_and_restore_roles() -> None:
    postgres = next(item for item in CONNECTORS if item.connector_id == "postgres")

    assert set(postgres.credential_env_vars) == {
        "DATABASE_URL",
        "DATABASE_PUBLIC_URL",
        "DATABASE_RESTORE_URL",
        "POSTGRES_ADMIN_URL",
    }
    assert postgres.configuration_env_vars == ("PGSSLROOTCERT",)
    assert {"api", "job2", "backup", "restore", "migration"} <= set(postgres.roles)


def test_catalog_covers_public_serving_and_operational_connectors() -> None:
    catalog = {connector.connector_id: connector for connector in CONNECTORS}

    assert catalog["frontend"].credential_class == "none"
    assert catalog["espn"].interface == "https_json_api_and_image_cdn"
    assert set(catalog["espn"].roles) == {
        "frontend",
        "frontend_live_scores",
        "frontend_player_images",
    }
    assert {"frontend", "operator", "scheduled_checks"} <= set(catalog["wnba_api"].roles)
    assert "recommendations" in catalog["wnba_api"].data_classification
    assert set(catalog["wnba_api"].configuration_env_vars) == {
        "VITE_API_URL",
        "WNBA_API_BASE",
    }

    assert catalog["watchdog_alert_sink"].credential_env_vars == ("WATCHDOG_PING_URL",)
    assert catalog["watchdog_heartbeat_sink"].credential_env_vars == ("WATCHDOG_HEARTBEAT_URL",)


def test_catalog_covers_control_plane_roles_without_values() -> None:
    catalog = {connector.connector_id: connector for connector in CONNECTORS}
    github = catalog["github_actions"]
    railway = catalog["railway"]
    realsports = catalog["realsports"]

    assert github.credential_env_vars == ("GH_TOKEN",)
    assert {"public_corpus_backup", "operations_issues"} <= set(github.roles)
    assert {"runtime_configuration", "runtime_secrets", "bounded_repair"} <= set(railway.roles)
    assert {
        "WNBA_RAILWAY_PROJECT_ID",
        "WNBA_RAILWAY_ENVIRONMENT_ID",
        "WNBA_RAILWAY_API_SERVICE_ID",
    } <= set(railway.configuration_env_vars)
    assert {
        "REAL_SPORTS_USERNAME",
        "REAL_SPORTS_PASSWORD",
        "REALSPORTS_STORAGE_STATE_B64GZ",
    } == set(realsports.credential_env_vars)
