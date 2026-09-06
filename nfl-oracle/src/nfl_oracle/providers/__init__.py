"""Observation-only Real Sports provider stubs (#91). No contest submission."""

from nfl_oracle.providers.auth_status import AuthProbeResult, probe_realsports_auth
from nfl_oracle.providers.five_card import (
    OFFLINE_RULE_NOTES,
    UNKNOWN_PROVIDER_RULES,
    FiveCardProviderStub,
    ProviderContractStatus,
    ProviderNotReady,
    offline_provider_rule_document,
)

__all__ = [
    "AuthProbeResult",
    "FiveCardProviderStub",
    "OFFLINE_RULE_NOTES",
    "ProviderContractStatus",
    "ProviderNotReady",
    "UNKNOWN_PROVIDER_RULES",
    "offline_provider_rule_document",
    "probe_realsports_auth",
]
