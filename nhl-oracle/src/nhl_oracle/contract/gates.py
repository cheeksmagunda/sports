"""NHL contract audit gates (always observation only, never contest entry).

Follows the hard-deny report shape of nfl-oracle's strategy/gates.py, but this
checklist is new for NHL: pool completeness, clock freshness, identity/goalie
eligibility, and boost regime are exactly issue #135's step 1 audit items,
expressed here as executable gates against a fixture rather than left as
prose. Gates run equally well against synthetic fixtures (today) and redacted
real fixtures (once the Week 1 authorization checkpoint is granted).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from nhl_oracle.contract.schema import BoostRegime, ContestFormat, LockScope, NhlAuditFixture


@dataclass(frozen=True)
class GateItem:
    key: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class NhlAuditReport:
    contest_entry: bool
    all_gates_ok: bool
    items: tuple[GateItem, ...]
    open_questions: tuple[str, ...]
    blocked_reasons: tuple[str, ...]

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "contest_entry": self.contest_entry,
            "all_gates_ok": self.all_gates_ok,
            "open_questions": list(self.open_questions),
            "blocked_reasons": list(self.blocked_reasons),
            "gates": [{"key": g.key, "ok": g.ok, "detail": g.detail} for g in self.items],
            "observation_only": True,
        }


def _aware(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp_must_be_timezone_aware")
    return parsed


def gate_pool_completeness(fixture: NhlAuditFixture) -> GateItem:
    """Require a priced pool large enough to fill the roster.

    When ``expected_pool_size`` or a games captured/scheduled pair is set, a
    five-card stub is not complete: the observed pool must equal the slate
    denominator and every scheduled game must be captured. Missing either
    games field, when the other is set, fails closed.
    """

    count = len(fixture.candidates)
    ids = [c.player_id for c in fixture.candidates]
    if len(set(ids)) != count:
        return GateItem(
            key="pool_completeness",
            ok=False,
            detail="duplicate_player_ids",
        )
    if fixture.games_scheduled is not None or fixture.games_captured is not None:
        scheduled = fixture.games_scheduled
        captured = fixture.games_captured
        if scheduled is None or captured is None or scheduled <= 0 or captured != scheduled:
            shown_captured = captured if captured is not None else "missing"
            shown_scheduled = scheduled if scheduled is not None else "missing"
            return GateItem(
                key="pool_completeness",
                ok=False,
                detail=f"games_incomplete_{shown_captured}_of_{shown_scheduled}",
            )
    missing_value = [c.player_id for c in fixture.candidates if c.score_value is None]
    target = fixture.expected_pool_size
    if target is not None:
        if target < fixture.expected_roster_size or count != target:
            return GateItem(
                key="pool_completeness",
                ok=False,
                detail=f"pool_incomplete_{count}_of_{target}",
            )
    elif count < fixture.expected_roster_size:
        return GateItem(
            key="pool_completeness",
            ok=False,
            detail=f"pool_incomplete_{count}_of_{fixture.expected_roster_size}",
        )
    if missing_value:
        return GateItem(
            key="pool_completeness",
            ok=False,
            detail=f"missing_score_value_for_{len(missing_value)}_candidates",
        )
    return GateItem(key="pool_completeness", ok=True, detail="pool_complete")


def gate_clock_freshness(fixture: NhlAuditFixture, *, decision_at: datetime) -> GateItem:
    if decision_at.tzinfo is None:
        raise ValueError("decision_at_must_be_timezone_aware")
    stale = [c.player_id for c in fixture.candidates if _aware(c.captured_at) > decision_at]
    if stale:
        return GateItem(
            key="clock_freshness",
            ok=False,
            detail=f"future_capture_for_{len(stale)}_candidates",
        )
    return GateItem(key="clock_freshness", ok=True, detail="all_captures_before_decision")


def gate_identity_resolution(fixture: NhlAuditFixture) -> GateItem:
    unresolved = [c.player_id for c in fixture.candidates if not c.identity_resolved]
    ambiguous = [c.player_id for c in fixture.candidates if c.identity_ambiguous]
    if unresolved:
        return GateItem(
            key="identity_resolution",
            ok=False,
            detail=f"unresolved_identity_for_{len(unresolved)}_candidates",
        )
    if ambiguous:
        return GateItem(
            key="identity_resolution",
            ok=False,
            detail=f"ambiguous_identity_for_{len(ambiguous)}_candidates",
        )
    return GateItem(key="identity_resolution", ok=True, detail="all_identities_resolved")


def gate_boost_regime(fixture: NhlAuditFixture) -> GateItem:
    contract = fixture.contract
    if contract.boost_regime is BoostRegime.UNKNOWN:
        return GateItem(key="boost_regime", ok=False, detail="boost_regime_unconfirmed")
    if contract.format is ContestFormat.FIVE_CARD_ORDERED:
        if contract.slot_multipliers is None:
            return GateItem(
                key="boost_regime",
                ok=False,
                detail="slot_multipliers_missing_for_five_card_format",
            )
        if len(contract.slot_multipliers) != contract.roster_size:
            return GateItem(key="boost_regime", ok=False, detail="slot_multipliers_length_mismatch")
    return GateItem(key="boost_regime", ok=True, detail="boost_regime_confirmed")


def gate_zero_boost_until_all_teams_played(fixture: NhlAuditFixture) -> GateItem:
    """Hard deny boosted regimes while any team is still at 0 GP this season.

    Strategy: through the early-slate / all-teams-played gap, boost multiplier
    stays 0. Missing coverage fails closed (gate not cleared).
    """

    from nhl_oracle.contract.boost_gate import evaluate_boost_eligibility

    eligibility = evaluate_boost_eligibility(fixture.team_games_played)
    if not eligibility.boost_allowed:
        if fixture.contract.boost_regime is not BoostRegime.NONE:
            return GateItem(
                key="zero_boost_until_all_teams_played",
                ok=False,
                detail=(
                    f"boost_regime_{fixture.contract.boost_regime.value}_blocked; "
                    f"{eligibility.detail}"
                ),
            )
        return GateItem(
            key="zero_boost_until_all_teams_played",
            ok=True,
            detail=eligibility.detail,
        )
    return GateItem(
        key="zero_boost_until_all_teams_played",
        ok=True,
        detail=eligibility.detail,
    )


def gate_lock_scope(fixture: NhlAuditFixture) -> GateItem:
    if fixture.contract.lock_scope is LockScope.UNKNOWN:
        return GateItem(key="lock_scope", ok=False, detail="lock_scope_unconfirmed")
    return GateItem(key="lock_scope", ok=True, detail="lock_scope_confirmed")


def evaluate_nhl_audit(fixture: NhlAuditFixture, *, decision_at: datetime) -> NhlAuditReport:
    """Evaluate the full audit checklist; never signals contest entry readiness."""

    items = (
        gate_pool_completeness(fixture),
        gate_clock_freshness(fixture, decision_at=decision_at),
        gate_identity_resolution(fixture),
        gate_boost_regime(fixture),
        gate_zero_boost_until_all_teams_played(fixture),
        gate_lock_scope(fixture),
    )
    blocked = tuple(item.key for item in items if not item.ok)
    return NhlAuditReport(
        contest_entry=False,
        all_gates_ok=not blocked,
        items=items,
        open_questions=fixture.contract.open_questions(),
        blocked_reasons=blocked,
    )
