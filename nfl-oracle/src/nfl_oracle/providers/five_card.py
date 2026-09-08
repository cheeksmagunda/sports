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
            "provider_contract_verified": False,
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

# Offline / public-rules documentation only. Best-effort notes from Drive NFL
# strategy playbook + 2026-09-02 empirical findings on *finalized* contests.
# Documenting a rule here does NOT remove it from UNKNOWN_PROVIDER_RULES and
# does NOT enable submit, inventory fetch, or contest entry.
OFFLINE_RULE_NOTES: dict[str, str] = {
    "provider_roster_and_inventory_eligibility": (
        "Best-effort: finalized contests expose draftable pools via draftinfo / "
        "search and per-game /players rosters; full two-team depth is not the "
        "fantasy-eligible subset. Pre-lock inventory eligibility, ownership "
        "caps, and card-availability gates remain unverified — no live slate "
        "inventory fetch in this package."
    ),
    "provider_duplicate_card_rules": (
        "Best-effort: structural shadow checks reject duplicate player_ids in a "
        "five-card set (5 distinct Real ids). Whether the provider additionally "
        "forbids duplicate cards across concurrent entries, shared inventory, or "
        "boost stacking is unverified against live Real Sports."
    ),
    "slot_weights_and_scoring": (
        "Best-effort public/offline: OBSERVED_DEFAULT_SLOT_MULTIPLIERS "
        "[2.0, 1.8, 1.6, 1.4, 1.2] from draftinfo defaultMultipliers (contests "
        "1069/870/1070; byte-identical on non-NFL 2124). Formula (non-negative): "
        "item_score = value * (slot_multiplier + multiplierBonus). Prefer "
        "per-contest defaultMultipliers when available. Still unverified as a "
        "closed #91 provider contract — shadow algebra only."
    ),
    "provider_lock_semantics": (
        "Best-effort: playbook requires decision_at < lock_at when lock is known; "
        "WNBA used earliest tip as a lock *proxy* only. No pre-lock NFL contest "
        "state has been captured; exact Real Sports NFL lock timestamp field, "
        "late-scratch behavior, and post-lock mutation rules remain unknown."
    ),
    "multiplier_bonus_pre_lock_visibility": (
        "Best-effort empirical: finalized contest stats populate multiplierBonus "
        "(0..3.0 step 0.1; higher boosts on lower-ranked players per "
        "descriptionText). Pregame search observed uniform zeros — historical "
        "finalized boosts do NOT prove pre-lock visibility. Feature "
        "card_boost_post_settlement stays live_ok=false until proven."
    ),
    "negative_value_scoring_branch": (
        "Best-effort: non-negative branch verified exactly on observed NFL "
        "finalized lineups. A non-NFL row showed value=-0.6442 with score equal "
        "to value despite multiplier=4.9 (multiplier did not amplify). Offline "
        "contest_shadow_score refuses the non-negative formula on negatives "
        "unless allow_unresolved_negative=True. Live provider branch unverified."
    ),
    "submission_payload_shape": (
        "Best-effort: finalized /entries lineup items expose playerId, order "
        "(0..4), multiplier, multiplierBonus, value, score. That is a "
        "*settlement* shape, not a proven submit body. No NFL contest entry "
        "POST has been issued from this package; payload keys, auth headers, "
        "and idempotency remain unknown. submit() hard-denies."
    ),
}


def offline_provider_rule_document() -> dict[str, Any]:
    """Machine-readable offline notes for UNKNOWN_PROVIDER_RULES (no submit)."""

    return {
        "name": "nfl_unknown_provider_rules_offline_notes",
        "version": 1,
        "contest_entry": False,
        "observation_only": True,
        "provider_contract_verified": False,
        "submit_enabled": False,
        "issue_refs": ["#89", "#91"],
        "unknown_rules": list(UNKNOWN_PROVIDER_RULES),
        "offline_rule_notes": dict(OFFLINE_RULE_NOTES),
        "note": (
            "Notes are best-effort public/offline documentation only. Presence "
            "of a note does not close the rule or authorize contest entry."
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
