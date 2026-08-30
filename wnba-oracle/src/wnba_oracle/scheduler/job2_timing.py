"""Job 2 freeze-timing gates.

Extracted from job2.py. Pure time arithmetic: no DB, no Redis, no
logging. Given the slate's lock/tip time and the current UTC clock,
these decide whether a fire is pre-window, freeze-eligible, or gated
out of the late re-freeze. See job2.run for how the gates compose.
"""

from __future__ import annotations

import datetime as dt

from wnba_oracle.common.feature_payload import parse_feature_mapping


def _game_start_utc(row: dict) -> dt.datetime | None:
    """The tip time of this pool row's game, from features_json (D109).

    None when job1 persisted the row without one (pre-D109 enrichment, or a
    platform payload with no dateTime). Callers that scope the pool treat
    None as "cannot verify", not as "not started".
    """
    feats, _invalid = parse_feature_mapping(row.get("features_json"))
    raw = str(feats.get("game_start_utc") or "").strip()
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def scope_to_upcoming_games(
    rows: list[dict], now_utc: dt.datetime
) -> tuple[list[dict], dt.datetime | None, int, int]:
    """Keep only players whose game has not tipped yet (D109).

    A WNBA slate spans several tip times. Once the early game starts its
    players are no longer enterable, so an operator drafting late needs a
    pool drawn from the games still ahead. Fails closed: a row with no
    known game start is dropped, because "has not started" cannot be
    verified for it.

    Returns (kept rows, earliest remaining tip, n_started, n_unknown).
    """
    kept: list[dict] = []
    n_started = n_unknown = 0
    earliest: dt.datetime | None = None
    for r in rows:
        start = _game_start_utc(r)
        if start is None:
            n_unknown += 1
            continue
        if start <= now_utc:
            n_started += 1
            continue
        kept.append(r)
        if earliest is None or start < earliest:
            earliest = start
    return kept, earliest, n_started, n_unknown


def _freeze_deadline_utc(
    lock_time_utc: dt.datetime | None,
    settings,
) -> dt.datetime | None:
    """The tip-relative freeze deadline = lock/first-tip minus freeze_lead_minutes.

    WNBA slates tip at different clock times each day, so a static UTC cutoff
    (late_refreeze_after_utc) misses an afternoon slate that locks before the
    evening cron window. The deadline anchors freeze timing to the slate's own
    first tip. None when slate_meta has no timing (callers fall back to their
    static behaviour). See deep-dive E.
    """
    if lock_time_utc is None:
        return None
    lead = int(getattr(settings, "freeze_lead_minutes", 40))
    return lock_time_utc - dt.timedelta(minutes=lead)


def _in_pre_freeze_window(now_utc: dt.datetime, deadline_utc: dt.datetime | None) -> bool:
    """True when this fire should be skipped because the slate has not reached
    its T-minus freeze deadline yet. A None deadline (tip unknown) never skips:
    the static late-refreeze fallback handles timing in that case. See E."""
    return deadline_utc is not None and now_utc < deadline_utc


def _late_refreeze_allowed(
    now_utc: dt.datetime,
    lock_time_utc: dt.datetime | None,
    settings,
) -> tuple[bool, str]:
    """D83 lock gate for the late re-freeze.

    Lock time known: allow only strictly before lock minus the buffer.
    Lock time unknown: allow only strictly before the configured hard
    deadline (HH:MM UTC). A malformed deadline blocks the re-freeze;
    failing closed is the point of the gate.
    """
    if lock_time_utc is not None:
        buffer = dt.timedelta(minutes=int(settings.refreeze_lock_buffer_min))
        if now_utc < lock_time_utc - buffer:
            return True, "pre_lock"
        return False, "lock_gated"
    try:
        h, m = (int(x) for x in settings.late_refreeze_deadline_utc.split(":"))
        deadline = now_utc.replace(hour=h, minute=m, second=0, microsecond=0)
    except (ValueError, AttributeError):
        return False, "bad_deadline_config"
    if now_utc < deadline:
        return True, "pre_deadline_no_locktime"
    return False, "deadline_no_locktime"
