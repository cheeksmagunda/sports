"""Stable, value-free map of the WNBA application's connector boundaries.

The catalog names interfaces and credential classes, never configured values,
mutable service identifiers, request URLs, headers, or provider payloads. A
freeze records only the decision-input connector IDs and their subset digest,
so serving and control-plane changes cannot look like model-input changes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Final

CONNECTOR_CATALOG_SCHEMA_VERSION: Final = 1


@dataclass(frozen=True)
class ConnectorSpec:
    """One stable application boundary, with no runtime configuration values."""

    connector_id: str
    plane: str
    direction: str
    interface: str
    data_classification: str
    credential_class: str
    criticality: str
    affects_decision: bool
    credential_env_vars: tuple[str, ...]
    configuration_env_vars: tuple[str, ...]
    roles: tuple[str, ...]
    failure_semantics: str

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["credential_env_vars"] = list(self.credential_env_vars)
        payload["configuration_env_vars"] = list(self.configuration_env_vars)
        payload["roles"] = list(self.roles)
        return payload


CONNECTORS: Final[tuple[ConnectorSpec, ...]] = (
    ConnectorSpec(
        connector_id="realsports",
        plane="data",
        direction="ingress",
        interface="https",
        data_classification="public_sports_data",
        credential_class="derived_session_or_legacy_password",
        criticality="required",
        affects_decision=True,
        credential_env_vars=(
            "REAL_SPORTS_USERNAME",
            "REAL_SPORTS_PASSWORD",
            "REALSPORTS_STORAGE_STATE_B64GZ",
        ),
        configuration_env_vars=("WNBA_DEVICE_UUID", "WNBA_DEVICE_NAME"),
        roles=("job1", "job1games", "dayclose"),
        failure_semantics="required_work_fails",
    ),
    ConnectorSpec(
        connector_id="rotowire",
        plane="data",
        direction="ingress",
        interface="https_html",
        data_classification="public_sports_data",
        credential_class="none",
        criticality="optional",
        affects_decision=True,
        credential_env_vars=(),
        configuration_env_vars=(),
        roles=("job1", "job1late"),
        failure_semantics="optional_signal_degrades",
    ),
    ConnectorSpec(
        connector_id="the_odds_api",
        plane="data",
        direction="ingress",
        interface="https_json",
        data_classification="public_sports_data",
        credential_class="api_key",
        criticality="optional",
        affects_decision=True,
        credential_env_vars=("ODDS_API_KEY",),
        configuration_env_vars=(),
        roles=("job1",),
        failure_semantics="optional_signal_degrades",
    ),
    ConnectorSpec(
        connector_id="wnba_stats",
        plane="data",
        direction="ingress",
        interface="https_via_nba_api",
        data_classification="public_sports_data",
        credential_class="none",
        criticality="role_dependent",
        affects_decision=True,
        credential_env_vars=(),
        configuration_env_vars=(),
        roles=("job1", "dayclose"),
        failure_semantics="job1_signal_degrades_dayclose_enabled_refresh_fails",
    ),
    ConnectorSpec(
        connector_id="postgres",
        plane="state",
        direction="bidirectional",
        interface="postgresql",
        data_classification="public_data_application_state",
        credential_class="managed_connection_url",
        criticality="required",
        affects_decision=True,
        credential_env_vars=(
            "DATABASE_URL",
            "DATABASE_PUBLIC_URL",
            "DATABASE_RESTORE_URL",
            "POSTGRES_ADMIN_URL",
        ),
        configuration_env_vars=("PGSSLROOTCERT",),
        roles=(
            "api",
            "job1",
            "job1games",
            "job1late",
            "job2",
            "dayclose",
            "backfill",
            "backup",
            "restore",
            "migration",
            "migration_acceptance",
        ),
        failure_semantics="required_durable_work_fails",
    ),
    ConnectorSpec(
        connector_id="redis",
        plane="state",
        direction="bidirectional",
        interface="redis",
        data_classification="public_data_coordination_state",
        credential_class="managed_connection_url",
        criticality="coordination",
        affects_decision=False,
        credential_env_vars=("REDIS_URL",),
        configuration_env_vars=(),
        roles=("api", "job2"),
        failure_semantics="coordination_degrades_to_postgres_guard",
    ),
    ConnectorSpec(
        connector_id="model_artifact",
        plane="data",
        direction="ingress",
        interface="verified_local_file",
        data_classification="derived_public_sports_data",
        credential_class="none",
        criticality="required",
        affects_decision=True,
        credential_env_vars=(),
        configuration_env_vars=(
            "WNBA_ORACLE_MODEL_ARTIFACT_SHA",
            "WNBA_ORACLE_MODEL_CHALLENGER_SHA",
        ),
        roles=("job2",),
        failure_semantics="production_job_fails_closed",
    ),
    ConnectorSpec(
        connector_id="identity_override_file",
        plane="data",
        direction="ingress",
        interface="optional_local_csv",
        data_classification="operator_curated_public_player_identity_mapping",
        credential_class="none",
        criticality="optional",
        affects_decision=True,
        credential_env_vars=(),
        configuration_env_vars=(),
        roles=("job1",),
        failure_semantics="absence_uses_public_catalog_malformed_rows_are_ignored",
    ),
    ConnectorSpec(
        connector_id="payout_archive",
        plane="data",
        direction="ingress",
        interface="optional_local_json",
        data_classification="public_contest_payout_schedule",
        credential_class="none",
        criticality="optional",
        affects_decision=True,
        credential_env_vars=(),
        configuration_env_vars=(),
        roles=("job2",),
        failure_semantics="absence_or_invalid_file_uses_configured_default_regime",
    ),
    ConnectorSpec(
        connector_id="wnba_api",
        plane="serving",
        direction="egress",
        interface="https_json",
        data_classification=(
            "public_sports_recommendations_model_provenance_freeze_history_and_operational_status"
        ),
        credential_class="none",
        criticality="serving",
        affects_decision=False,
        credential_env_vars=(),
        configuration_env_vars=("VITE_API_URL", "WNBA_API_BASE"),
        roles=("api", "frontend", "operator", "scheduled_checks"),
        failure_semantics="read_surface_unavailable",
    ),
    ConnectorSpec(
        connector_id="frontend",
        plane="serving",
        direction="consumer",
        interface="https",
        data_classification="public_sports_recommendations_and_operational_status",
        credential_class="none",
        criticality="serving",
        affects_decision=False,
        credential_env_vars=(),
        configuration_env_vars=(),
        roles=("frontend",),
        failure_semantics="display_unavailable_model_pipeline_independent",
    ),
    ConnectorSpec(
        connector_id="espn",
        plane="serving",
        direction="ingress",
        interface="https_json_api_and_image_cdn",
        data_classification="public_live_sports_data_and_player_images",
        credential_class="none",
        criticality="optional",
        affects_decision=False,
        credential_env_vars=(),
        configuration_env_vars=(),
        roles=("frontend", "frontend_live_scores", "frontend_player_images"),
        failure_semantics="optional_display_enrichment_degrades_model_pipeline_independent",
    ),
    ConnectorSpec(
        connector_id="github_actions",
        plane="control",
        direction="bidirectional",
        interface="git_https_and_cli",
        data_classification="private_source_code_public_corpus_and_operational_metadata",
        credential_class="native_or_managed_identity",
        criticality="control_plane",
        affects_decision=False,
        credential_env_vars=("GH_TOKEN",),
        configuration_env_vars=(),
        roles=("ci", "scheduled_checks", "public_corpus_backup", "operations_issues"),
        failure_semantics=("ci_or_deployment_delayed_public_backup_stale_or_issue_escalation_lost"),
    ),
    ConnectorSpec(
        connector_id="railway",
        plane="control",
        direction="bidirectional",
        interface="native_cli_and_graphql_https",
        data_classification=("deployment_runtime_configuration_secrets_and_operational_metadata"),
        credential_class="native_or_scoped_identity",
        criticality="runtime",
        affects_decision=False,
        credential_env_vars=("RAILWAY_TOKEN", "RAILWAY_WORKSPACE_TOKEN"),
        configuration_env_vars=(
            "WNBA_EXPECTED_MODEL_SHA",
            "WNBA_RAILWAY_PROJECT_ID",
            "WNBA_RAILWAY_ENVIRONMENT_ID",
            "WNBA_RAILWAY_API_SERVICE_ID",
            "WNBA_RAILWAY_JOB1_SERVICE_ID",
            "WNBA_RAILWAY_JOB1_LATE_SERVICE_ID",
            "WNBA_RAILWAY_JOB2_SERVICE_ID",
            "WNBA_RAILWAY_DAYCLOSE_SERVICE_ID",
        ),
        roles=(
            "deployment",
            "runtime",
            "runtime_configuration",
            "runtime_secrets",
            "scheduled_checks",
            "bounded_repair",
        ),
        failure_semantics=("deployment_runtime_scheduled_check_or_bounded_repair_unavailable"),
    ),
    ConnectorSpec(
        connector_id="watchdog_alert_sink",
        plane="operations",
        direction="egress",
        interface="https",
        data_classification="operational_status",
        credential_class="secret_url",
        criticality="optional",
        affects_decision=False,
        credential_env_vars=("WATCHDOG_PING_URL",),
        configuration_env_vars=(),
        roles=("runtime_watchdog_alert",),
        failure_semantics="best_effort_critical_event_delivery",
    ),
    ConnectorSpec(
        connector_id="watchdog_heartbeat_sink",
        plane="operations",
        direction="egress",
        interface="https",
        data_classification="operational_status",
        credential_class="secret_url",
        criticality="optional",
        affects_decision=False,
        credential_env_vars=("WATCHDOG_HEARTBEAT_URL",),
        configuration_env_vars=(),
        roles=("scheduled_watchdog_monitor",),
        failure_semantics="heartbeat_delivery_failure_marks_scheduled_monitor_alert",
    ),
    ConnectorSpec(
        connector_id="realsports_session_recovery",
        plane="operations",
        direction="operator_assisted",
        interface="ordinary_browser",
        data_classification="derived_session_only",
        credential_class="icloud_autofill",
        criticality="operator_recovery",
        affects_decision=False,
        credential_env_vars=(),
        configuration_env_vars=(),
        roles=("operator_recovery",),
        failure_semantics="authenticated_ingest_remains_unavailable",
    ),
)


def connector_catalog_payload(
    connectors: tuple[ConnectorSpec, ...] = CONNECTORS,
) -> dict[str, object]:
    """Return the canonical, JSON-serializable catalog ordered by stable ID."""

    return {
        "schema_version": CONNECTOR_CATALOG_SCHEMA_VERSION,
        "connectors": [
            connector.to_payload()
            for connector in sorted(connectors, key=lambda item: item.connector_id)
        ],
    }


def decision_input_connector_catalog_payload(
    connectors: tuple[ConnectorSpec, ...] = CONNECTORS,
) -> dict[str, object]:
    """Return only connectors capable of changing recommendation inputs."""

    return connector_catalog_payload(
        tuple(connector for connector in connectors if connector.affects_decision)
    )


def _catalog_sha256(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


DECISION_INPUT_CONNECTOR_IDS: Final = tuple(
    sorted(connector.connector_id for connector in CONNECTORS if connector.affects_decision)
)
CONNECTOR_CATALOG_SHA256: Final = _catalog_sha256(connector_catalog_payload())
DECISION_INPUT_CONNECTOR_CATALOG_SHA256: Final = _catalog_sha256(
    decision_input_connector_catalog_payload()
)
