"""WNBA-owned connector inventory and observational source assurance."""

from wnba_oracle.assurance.connectors import (
    CONNECTOR_CATALOG_SCHEMA_VERSION,
    CONNECTOR_CATALOG_SHA256,
    CONNECTORS,
    DECISION_INPUT_CONNECTOR_CATALOG_SHA256,
    DECISION_INPUT_CONNECTOR_IDS,
    ConnectorSpec,
    connector_catalog_payload,
    decision_input_connector_catalog_payload,
)
from wnba_oracle.assurance.source_quality import (
    SOURCE_ASSURANCE_SCHEMA_VERSION,
    build_source_assurance,
    unknown_source_assurance,
)

__all__ = [
    "CONNECTORS",
    "CONNECTOR_CATALOG_SCHEMA_VERSION",
    "CONNECTOR_CATALOG_SHA256",
    "DECISION_INPUT_CONNECTOR_CATALOG_SHA256",
    "DECISION_INPUT_CONNECTOR_IDS",
    "SOURCE_ASSURANCE_SCHEMA_VERSION",
    "ConnectorSpec",
    "build_source_assurance",
    "connector_catalog_payload",
    "decision_input_connector_catalog_payload",
    "unknown_source_assurance",
]
