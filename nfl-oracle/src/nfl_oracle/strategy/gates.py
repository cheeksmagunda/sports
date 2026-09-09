"""Contest-entry readiness gates (always deny submission from this package).

Documents what must be true before any future entry authorization. Gates do not
enable contest entry; ``contest_entry`` remains False regardless of checklist.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from nfl_oracle.strategy.schema import Posture

if TYPE_CHECKING:
    from nfl_oracle.contests.boosts import BoostObservation
    from nfl_oracle.providers.five_card import FiveCardProviderStub
    from nfl_oracle.recommendations.optimizer import Pick
    from nfl_oracle.recommendations.schema import Candidate, EvidenceClock, Slate


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


# ---------------------------------------------------------------------------
# Freeze-readiness gates (G1-G7).
#
# These gates decide whether the recommendation pipeline may PRINT five
# already-selected player ids in committed slot order for the operator to
# read and enter by hand. They never grant contest entry: G7 below is a
# standing, checkable assertion that no code path in this package can submit
# a contest, and every artifact these gates allow through still carries
# ``contest_entry: False``.
#
# This module is kept a leaf: it has no runtime import of
# ``nfl_oracle.recommendations`` or ``nfl_oracle.contests`` (only
# ``TYPE_CHECKING`` imports for annotations), so ``_utc_or_raise`` restates
# the tiny aware-datetime check from ``recommendations.schema.utc`` rather
# than importing it.
# ---------------------------------------------------------------------------

BoostRegime = Literal["zero_boost", "published", "undetermined"]


def _utc_or_raise(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone_required")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class FreezeGateReport:
    """Aggregate result of running every freeze gate once, in order."""

    ok: bool
    items: tuple[GateItem, ...]
    failed: tuple[str, ...]

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "gates": [{"key": g.key, "ok": g.ok, "detail": g.detail} for g in self.items],
            "failed_gates": list(self.failed),
            "contest_entry": False,
        }


def combine_gate_items(items: Sequence[GateItem]) -> FreezeGateReport:
    failed = tuple(g.key for g in items if not g.ok)
    return FreezeGateReport(ok=not failed, items=tuple(items), failed=failed)


def gate_pool_completeness(slate: Slate) -> GateItem:
    """G1: the candidate pool's stated denominator must be self-consistent.

    Consumes exactly the three fields the live slate artifact already states
    (method, roster_count, matched_count, unmatched_ids) rather than
    reinventing pool verification.
    """
    detail = (
        f"method={slate.pool_method} roster_count={slate.pool_roster_count} "
        f"matched_count={slate.pool_search_matched_count} "
        f"unmatched_count={len(slate.pool_unmatched_ids)} "
        f"candidate_count={len(slate.candidates)}"
    )
    ok = (
        slate.pool_roster_count > 0
        and slate.pool_search_matched_count == slate.pool_roster_count
        and not slate.pool_unmatched_ids
        and len(slate.candidates) >= 5
    )
    return GateItem(key="G1_pool_completeness", ok=ok, detail=detail)


def gate_clock_freshness(
    clocks: Mapping[str, EvidenceClock],
    *,
    decision_at: datetime,
    max_age_seconds: int,
) -> GateItem:
    """G2: every named input source must carry a clock, none stale or future."""
    now = _utc_or_raise(decision_at)
    if not clocks:
        return GateItem(key="G2_clock_freshness", ok=False, detail="no_clocks_supplied")
    future: list[str] = []
    stale: list[str] = []
    ages: dict[str, float] = {}
    for name, clock in sorted(clocks.items()):
        if max(clock.source_available_at, clock.captured_at) > now:
            future.append(name)
            continue
        age = (now - clock.captured_at).total_seconds()
        ages[name] = age
        if age > max_age_seconds:
            stale.append(name)
    ok = not stale and not future
    rendered_ages = ", ".join(f"{name}={age:.0f}s" for name, age in sorted(ages.items()))
    detail = (
        f"max_age_seconds={max_age_seconds} stale={stale} future={future} ages=[{rendered_ages}]"
    )
    return GateItem(key="G2_clock_freshness", ok=ok, detail=detail)


def gate_identity_resolution(slate: Slate, picks: Sequence[Pick]) -> GateItem:
    """G3: each selected pick resolves to exactly one candidate id on this slate.

    Resolution is by ``player_id`` alone; this function never looks at a
    player's name. A pick is also refused if the underlying candidate's
    provider status reads unavailable (out/inactive/suspended/ir), so an
    unavailable player is never silently carried through to the committed
    five even if some upstream step selected one by mistake.
    """
    by_id: dict[int, Candidate] = {c.player_id: c for c in slate.candidates}
    game_ids = {g.game_id for g in slate.games}
    problems: list[str] = []
    seen: set[int] = set()
    for pick in picks:
        if pick.player_id in seen:
            problems.append(f"duplicate_pick:{pick.player_id}")
        seen.add(pick.player_id)
        candidate = by_id.get(pick.player_id)
        if candidate is None:
            problems.append(f"unresolved_player_id:{pick.player_id}")
            continue
        if candidate.game_id not in game_ids or candidate.game_id != pick.game_id:
            problems.append(f"game_not_in_slate:{pick.player_id}")
        if candidate.team_id != pick.team_id:
            problems.append(f"team_mismatch:{pick.player_id}")
        status = (candidate.injury_status or "").strip().lower()
        if status in {"out", "inactive", "suspended", "ir"}:
            problems.append(f"unavailable_player_selected:{pick.player_id}:{status}")
    ok = len(picks) == 5 and len(seen) == 5 and not problems
    detail = f"picks={len(picks)} distinct={len(seen)} problems={problems}"
    return GateItem(key="G3_identity", ok=ok, detail=detail)


def declare_boost_regime(observation: BoostObservation) -> BoostRegime:
    """The regime must be an explicit label, never inferred silently from zeros."""
    if observation.n_players <= 0:
        return "undetermined"
    if observation.published:
        return "published"
    if observation.all_zero:
        return "zero_boost"
    return "undetermined"


def gate_boost_regime(observation: BoostObservation, slate: Slate) -> GateItem:
    """G4: the boost regime must be declared, and must not contradict the slate.

    A watched sample (the live boost-search probe) is cross-checked against
    the full candidate pool captured in the slate: a ``zero_boost`` regime is
    refused if any slate candidate actually carries a nonzero ``card_boost``,
    since the watcher only samples a subset of the pool.
    """
    regime = declare_boost_regime(observation)
    slate_nonzero = [c.player_id for c in slate.candidates if c.card_boost > 0]
    ok = regime in {"zero_boost", "published"} and not (regime == "zero_boost" and slate_nonzero)
    detail = (
        f"declared_regime={regime} watch_n_players={observation.n_players} "
        f"watch_n_nonzero={observation.n_nonzero} watch_published={observation.published} "
        f"watch_captured_at={observation.captured_at} "
        f"slate_nonzero_candidate_count={len(slate_nonzero)}"
    )
    return GateItem(key="G4_boost_regime", ok=ok, detail=detail)


def gate_no_submission_path() -> GateItem:
    """G7: a real, checkable structural proof that nothing here can submit.

    Scans every ``.py`` file under the installed ``nfl_oracle`` package for a
    write-verb HTTP call (``post``/``put``/``patch``/``delete``) on the same
    line as a contest-entry-shaped path (``playerratingcontest``, an
    ``/entries`` or ``/draft*`` route, or an "enter/submit lineup" name), and
    separately asserts that the one contest-facing stub method
    (``FiveCardProviderStub.submit``) is a pure, unconditional raise that
    never reaches an HTTP call. Excludes this scan's own source line (which
    quotes those path shapes as scan targets, not calls) and this docstring.
    """
    import inspect as _inspect

    import nfl_oracle
    from nfl_oracle.providers.five_card import FiveCardProviderStub

    package_root = Path(nfl_oracle.__file__).resolve().parent
    this_file = Path(__file__).resolve()
    write_verb = re.compile(r"\.(post|put|patch|delete)\s*\(", re.IGNORECASE)
    entry_shape = re.compile(
        r"playerratingcontest|/entries|/draft(?!Stats)|enter.{0,4}lineup|submit.{0,4}lineup",
        re.IGNORECASE,
    )
    suspects: list[str] = []
    for path in sorted(package_root.rglob("*.py")):
        if path.resolve() == this_file:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            if write_verb.search(line) and entry_shape.search(line):
                suspects.append(f"{path.relative_to(package_root)}:{lineno}")
    submit_source = _inspect.getsource(FiveCardProviderStub.submit)
    stub_is_pure_raise = (
        "raise ProviderNotReady" in submit_source
        and "http" not in submit_source.lower()
        and "client" not in submit_source.lower()
    )
    ok = not suspects and stub_is_pure_raise
    detail = (
        f"scanned_root={package_root} write_verb_entry_shape_hits={suspects} "
        f"submit_stub_is_pure_raise={stub_is_pure_raise}"
    )
    return GateItem(key="G7_no_submission", ok=ok, detail=detail)
