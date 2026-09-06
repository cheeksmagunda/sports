"""Derive strategy posture from provider readiness (observation only)."""

from __future__ import annotations

from nfl_oracle.providers.five_card import (
    FiveCardProviderStub,
    ProviderContractStatus,
    ProviderReadiness,
)
from nfl_oracle.strategy.schema import Posture


def posture_from_readiness(ready: ProviderReadiness) -> Posture:
    """Map stub readiness to strategy Posture without enabling contest entry."""

    if ready.contest_entry:
        # Defensive: stub always sets contest_entry=False.
        return Posture.BLOCKED
    if ready.status == ProviderContractStatus.AUTH_MISSING:
        return Posture.BLOCKED
    if ready.status == ProviderContractStatus.STUB:
        return Posture.SHADOW_ONLY
    if ready.status == ProviderContractStatus.UNVERIFIED:
        return Posture.READY_PENDING_CONTRACT
    if ready.status == ProviderContractStatus.VERIFIED:
        # Verified contract still does not authorize entry from this package.
        return Posture.CAPTURE_ONLY
    return Posture.SHADOW_ONLY


def current_posture(*, stub: FiveCardProviderStub | None = None) -> Posture:
    provider = stub or FiveCardProviderStub()
    return posture_from_readiness(provider.readiness())
