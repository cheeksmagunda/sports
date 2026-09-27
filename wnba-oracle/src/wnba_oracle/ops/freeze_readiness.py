"""Advance freeze readiness summary (observation only).

Mirrors ``scripts/pre_freeze_guard.py`` fail-closed rules so one curl on
``/watchdog/{slate_date}`` answers whether job2 should trust the pipeline
before T-40. Hard blockers use **live** watchdog evaluation only so a
cleared tip-window ``no_job1_pool`` cannot sticky-block (#319 / #535).
Does not authorize Real Sports entry or manual lineup submit.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

# Keep in sync with pre_freeze_guard.HARD_WATCHDOG_TRIGGERS (imported below).
HARD_FREEZE_BLOCKERS: frozenset[str] = frozenset(
    {
        "enrichment_from_backfill",
        "job1_pool_degraded",
        "model_artifact_unresolved",
        "model_artifact_unset",
        "no_job1_pool",
        "pool_degenerate_teams",
        "pool_too_small",
    }
)

FreezeReadinessPhase = Literal[
    "paused",
    "already_frozen",
    "blocked",
    "advisory",
    "ready",
    "timing_unknown",
]


def _trigger_names(events: Iterable[Mapping[str, Any]]) -> set[str]:
    out: set[str] = set()
    for event in events:
        trigger = event.get("trigger")
        if isinstance(trigger, str) and trigger:
            out.add(trigger)
    return out


def triggers_from_watchdog_payload(
    events: Iterable[Mapping[str, Any]],
    history: Iterable[Mapping[str, Any]],
) -> set[str]:
    """Union live and cron-persisted triggers (display / advisory set)."""

    return _trigger_names(events) | _trigger_names(history)


def summarize_freeze_readiness(
    *,
    picks_paused: bool,
    slate_timing_captured: bool,
    lineup_frozen: bool,
    job1_status: str | None,
    job1_exit_code: int | None,
    events: Iterable[Mapping[str, Any]],
    history: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the additive ``freeze_readiness`` object for operator APIs.

    Hard blockers come from **live** watchdog evaluation only. Persisted
    ``history`` rows are informational: a tip-window ``no_job1_pool`` that
    later cleared must not sticky-block ``ready_for_freeze`` (#319 / #535).
    Non-hard triggers from live+history remain advisories.
    """

    live_triggers = _trigger_names(events)
    all_triggers = live_triggers | _trigger_names(history)
    blockers = sorted(HARD_FREEZE_BLOCKERS.intersection(live_triggers))
    advisories = sorted(all_triggers.difference(HARD_FREEZE_BLOCKERS))

    job1_status_l = str(job1_status or "").lower()
    # A mid-run / orphaned ``running`` row from redeploy thrash is not a
    # durable failure; only a completed non-success blocks.
    if job1_status is None or job1_status_l == "running":
        job1_ok: bool | None = None
    else:
        job1_ok = job1_status_l == "success" and job1_exit_code == 0

    if picks_paused:
        phase: FreezeReadinessPhase = "paused"
        ready = False
    elif lineup_frozen:
        phase = "already_frozen"
        ready = True
    elif blockers:
        phase = "blocked"
        ready = False
    elif not slate_timing_captured:
        phase = "timing_unknown"
        ready = False
    elif job1_ok is False:
        phase = "blocked"
        ready = False
    elif advisories:
        phase = "advisory"
        ready = True
    else:
        phase = "ready"
        ready = True

    return {
        "observation_only": True,
        "ready_for_freeze": ready,
        "phase": phase,
        "blockers": blockers,
        "advisories": advisories,
        "job1_last_status": job1_status,
        "job1_last_exit_code": job1_exit_code,
        "job1_success": job1_ok,
        "slate_timing_captured": slate_timing_captured,
        "picks_paused": picks_paused,
        "lineup_frozen": lineup_frozen,
        "policy": "fail_closed_matches_pre_freeze_guard",
    }
