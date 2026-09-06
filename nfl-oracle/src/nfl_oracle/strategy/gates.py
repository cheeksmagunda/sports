"""Contest-entry readiness gates (always deny submission from this package).

Documents what must be true before any future entry authorization. Gates do not
enable contest entry; ``contest_entry`` remains False regardless of checklist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from nfl_oracle.strategy.schema import Posture

if TYPE_CHECKING:
    from nfl_oracle.providers.five_card import FiveCardProviderStub


@dataclass(frozen=True)
class GateItem:
    key: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class EntryGateReport:
    contest_entry: bool
    posture: Posture
    all_research_gates_ok: bool
    items: tuple[GateItem, ...]
    blocked_reasons: tuple[str, ...]

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "contest_entry": self.contest_entry,
            "posture": self.posture.value,
            "all_research_gates_ok": self.all_research_gates_ok,
            "blocked_reasons": list(self.blocked_reasons),
            "gates": [{"key": g.key, "ok": g.ok, "detail": g.detail} for g in self.items],
            "policy": "submit_hard_denied_until_explicit_authorization",
            "observation_only": True,
        }


def evaluate_entry_gates(
    *,
    stub: FiveCardProviderStub | None = None,
    provider_contract_verified: bool = False,
    pre_lock_capture_proven: bool = False,
    submit_explicitly_authorized: bool = False,
) -> EntryGateReport:
    """Evaluate research readiness; never returns contest_entry=True."""

    # Local imports avoid strategy <-> providers circular import at package load.
    from nfl_oracle.providers.five_card import (
        FiveCardProviderStub,
        ProviderContractStatus,
    )
    from nfl_oracle.strategy.posture import posture_from_readiness

    provider = stub or FiveCardProviderStub()
    ready = provider.readiness()
    posture = posture_from_readiness(ready)

    items = (
        GateItem(
            key="realsports_auth_present",
            ok=ready.auth.usable,
            detail="storage_state or REALSPORTS_STORAGE_STATE_B64GZ present"
            if ready.auth.usable
            else "auth_missing_on_this_host",
        ),
        GateItem(
            key="provider_contract_verified",
            ok=provider_contract_verified and ready.status == ProviderContractStatus.VERIFIED,
            detail=(
                "live #91 five-card contract verified"
                if provider_contract_verified
                else "provider_contract_unverified_issue_91"
            ),
        ),
        GateItem(
            key="pre_lock_capture_proven",
            ok=pre_lock_capture_proven,
            detail=(
                "pre-lock contest state captured at least once"
                if pre_lock_capture_proven
                else "no_pre_lock_nfl_contest_state_ever_captured"
            ),
        ),
        GateItem(
            key="submit_explicitly_authorized",
            ok=submit_explicitly_authorized,
            detail=(
                "operator authorized contest entry"
                if submit_explicitly_authorized
                else "submit_not_authorized_by_policy"
            ),
        ),
        GateItem(
            key="package_submit_hard_deny",
            ok=False,
            detail="FiveCardProviderStub.submit always raises contest_entry_forbidden",
        ),
    )

    blocked = tuple(g.key for g in items if not g.ok)
    research_keys = {
        "realsports_auth_present",
        "provider_contract_verified",
        "pre_lock_capture_proven",
    }
    research_ok = all(g.ok for g in items if g.key in research_keys)

    return EntryGateReport(
        contest_entry=False,
        posture=posture,
        all_research_gates_ok=research_ok,
        items=items,
        blocked_reasons=blocked,
    )
