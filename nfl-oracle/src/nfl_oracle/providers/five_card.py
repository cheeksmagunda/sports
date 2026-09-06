"""Five-card Real Sports provider stub (#91). Observation / shadow only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from nfl_oracle.providers.auth_status import AuthProbeResult, probe_realsports_auth
from nfl_oracle.strategy.schema import FiveCardAction, LegalityCheck, check_action


class ProviderContractStatus(StrEnum):
    STUB = "stub"
    AUTH_MISSING = "auth_missing"
    UNVERIFIED = "unverified"
    # Verified would be set only after live contract proof against Real Sports.
    VERIFIED = "verified"


class ProviderNotReady(RuntimeError):
    """Raised when live provider calls are requested but contract/auth is not ready."""


@dataclass(frozen=True)
class ProviderReadiness:
    status: ProviderContractStatus
    contest_entry: bool
    auth: AuthProbeResult
    unknown_rules: tuple[str, ...]
    issue_refs: tuple[str, ...]

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "contest_entry": self.contest_entry,
            "auth": self.auth.to_json_obj(),
            "unknown_rules": list(self.unknown_rules),
            "offline_rule_notes": {
                k: OFFLINE_RULE_NOTES[k] for k in self.unknown_rules if k in OFFLINE_RULE_NOTES
            },
            "issue_refs": list(self.issue_refs),
            "observation_only": True,
        }


# Rules still unverified against live Real Sports (#91). Offline research may
# *observe* defaults (e.g. OBSERVED_DEFAULT_SLOT_MULTIPLIERS) without closing the
# provider contract — submit stays hard-denied regardless.
UNKNOWN_PROVIDER_RULES = (
    "provider_roster_and_inventory_eligibility",
    "provider_duplicate_card_rules",
    "slot_weights_and_scoring",  # offline observed defaults only; not provider-verified
    "provider_lock_semantics",
    "multiplier_bonus_pre_lock_visibility",
    "negative_value_scoring_branch",  # offline algebra has a documented non-negative branch
    "submission_payload_shape",
)

# Offline documentation only — does not remove keys from UNKNOWN_PROVIDER_RULES.
OFFLINE_RULE_NOTES: dict[str, str] = {
    "slot_weights_and_scoring": (
        "OBSERVED_DEFAULT_SLOT_MULTIPLIERS used for shadow algebra; live provider "
        "weights still unverified (#91)"
    ),
    "negative_value_scoring_branch": (
        "contest_shadow_score documents non-negative default branch offline; live "
        "provider branch unverified"
    ),
}


class FiveCardProviderStub:
    """Shadow-only adapter. Never submits contests or mutates provider state."""

    contest_entry: bool = False
    issue_refs: tuple[str, ...] = ("#89", "#91")

    def readiness(self) -> ProviderReadiness:
        auth = probe_realsports_auth()
        if not auth.usable:
            status = ProviderContractStatus.AUTH_MISSING
        else:
            # Auth material may exist elsewhere; contract still unverified here.
            status = ProviderContractStatus.UNVERIFIED
        return ProviderReadiness(
            status=status,
            contest_entry=False,
            auth=auth,
            unknown_rules=UNKNOWN_PROVIDER_RULES,
            issue_refs=self.issue_refs,
        )

    def validate_structural(self, action: FiveCardAction) -> LegalityCheck:
        return check_action(action)

    def fetch_slate_inventory(self, *, slate_id: str | None = None) -> dict[str, Any]:
        """Live inventory fetch is blocked until #91 contract is verified."""

        ready = self.readiness()
        raise ProviderNotReady(
            f"five_card_inventory_blocked status={ready.status.value} "
            f"slate_id={slate_id!r} contest_entry=false"
        )

    def shadow_preview(self, action: FiveCardAction) -> dict[str, Any]:
        """Offline preview of structural legality + readiness; no network I/O."""

        legality = self.validate_structural(action)
        ready = self.readiness()
        return {
            "contest_entry": False,
            "structurally_valid": legality.structurally_valid,
            "structural_errors": list(legality.structural_errors),
            "unknown_rules": list(legality.unknown_rules),
            "provider": ready.to_json_obj(),
            "player_ids": list(action.player_ids),
            "mode": "shadow_preview",
        }

    def submit(self, action: FiveCardAction) -> None:
        """Hard deny — contest entry is out of scope for this package."""

        del action
        raise ProviderNotReady("contest_entry_forbidden_by_nfl_oracle_policy")
