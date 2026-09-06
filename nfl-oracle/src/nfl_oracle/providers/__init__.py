"""Observation-only Real Sports provider stubs (#91). No contest submission."""

from nfl_oracle.providers.auth_status import AuthProbeResult, probe_realsports_auth
from nfl_oracle.providers.five_card import (
    FiveCardProviderStub,
    ProviderContractStatus,
    ProviderNotReady,
)

__all__ = [
    "AuthProbeResult",
    "FiveCardProviderStub",
    "ProviderContractStatus",
    "ProviderNotReady",
    "probe_realsports_auth",
]
