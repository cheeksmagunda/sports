"""Watchdog: pipeline-health checks + persistence + operator surface.

Each check is a deterministic SQL query against the canonical pipeline
tables (job1_enrichment + frozen_lineups). The checks run after every
cron-job2 fire so the most recent slate is always evaluated. Hits emit
a row into ``watchdog_events`` (severity warn/error/critical), a
structured log line tagged ``watchdog_event``, and surface on the
``/watchdog/today`` API endpoint so the operator can poll from a phone
without log access.

Triggers implemented (post-MVP, expand as the eval bundle grows):

- ``no_job1_pool`` (critical) — slate_date has zero job1_enrichment rows
  by the time the watchdog runs. Either cron-job1 failed or hasn't
  fired. The frontend will keep showing the countdown.
- ``pool_too_small`` (error, escalated from warn in D84) — fewer than 10
  enrichment rows (a normal WNBA slate has 60+ players). Indicates an
  ingest partial failure.
- ``pool_degenerate_teams`` (critical, D84) — enrichment rows exist but
  span fewer than 2 distinct teams. No valid slate has one team; a raw
  row count can miss this shape.
- ``enrichment_stale`` (warn, D84) — after 20:00 UTC the newest capture
  for today's slate predates the 13:00 UTC job1 fire window; job2 is
  about to freeze on yesterday's universe.
- ``no_frozen_lineup`` (critical) — no frozen row by the slate's freeze
  deadline (first_tip - freeze_lead_minutes when slate_meta has a tip,
  else the legacy 22:00 UTC fallback). The tip-relative form catches an
  afternoon slate that would lock before the evening cron window. Manual
  fire likely needed.
- ``missing_per_player`` (error) — frozen JSONB lacks the per_player
  block. The frontend will render placeholder cards. Should be
  impossible after D36, but the check is cheap and protects against
  future regressions.
- ``zero_expected_payout`` (warn) — lineup frozen with
  ``expected_payout = 0``. Optimizer either returned a degenerate
  solution or the payout curve was misconfigured. Operator should
  skip the contest.
- ``opponent_non_reciprocal`` (warn, #32) — job1_enrichment has a
  ``(team, opponent)`` edge that isn't mirrored back (A names B, B doesn't
  name A). A post-tip re-capture can overwrite ``opponent`` with a team's
  next fixture from the Odds API; downstream stacking already degrades
  safely to ``incomplete`` rather than trusting it, but the corruption
  should be caught same-day, not months later from a research scan.

Other writers reuse persist_events for out-of-run triggers:
``job1_pool_degraded`` (critical, job1's D84 sanity gate) and
``late_refreeze_gated`` (warn, job2's D83 lock gate).

When WATCHDOG_PING_URL is set, any critical event also fires a
best-effort GET to ``{url}/fail`` (dead-man's-switch paging, D84).

Each trigger writes at most once per (slate_date, trigger) tuple per
run to avoid log spam; persistence dedup is enforced by querying for
an existing row before INSERT.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field

from sqlalchemy import text

from wnba_oracle.common.logging import get_logger
from wnba_oracle.db.engine import get_engine

log = get_logger("oracle.watchdog")


SEVERITY_WARN = "warn"
SEVERITY_ERROR = "error"
SEVERITY_CRITICAL = "critical"


@dataclass(frozen=True)
class WatchdogEvent:
    slate_date: str
    trigger: str
    severity: str
    payload: dict = field(default_factory=dict)


WATCHDOG_INSERT = text(
    """
    INSERT INTO watchdog_events (
        slate_date, trigger, severity, payload_json, created_at
    ) VALUES (
        :slate_date, :trigger, :severity, CAST(:payload AS JSONB), now()
    )
    """
)

# De-dup: skip inserting a (slate_date, trigger) if one already fired in
# the last 6h. Same hit logged every 15 min from the cron loop would
# otherwise flood watchdog_events.
WATCHDOG_RECENT = text(
    """
    SELECT 1 FROM watchdog_events
    WHERE slate_date = :slate_date AND trigger = :trigger
      AND created_at > now() - INTERVAL '6 hours'
    LIMIT 1
    """
)


def persist_events(events: list[WatchdogEvent]) -> int:
    """Insert events, deduplicating within a 6h window per (slate, trigger)."""
    if not events:
        return 0
    eng = get_engine()
    n = 0
    with eng.begin() as conn:
        for ev in events:
            recent = conn.execute(
                WATCHDOG_RECENT,
                {"slate_date": ev.slate_date, "trigger": ev.trigger},
            ).first()
            if recent:
                log.info(
                    "watchdog_dedup",
                    slate_date=ev.slate_date,
                    trigger=ev.trigger,
                    severity=ev.severity,
                )
                continue
            conn.execute(
                WATCHDOG_INSERT,
                {
                    "slate_date": ev.slate_date,
                    "trigger": ev.trigger,
                    "severity": ev.severity,
                    "payload": json.dumps(ev.payload),
                },
            )
            n += 1
            log.warning(
                "watchdog_event",
                slate_date=ev.slate_date,
                trigger=ev.trigger,
                severity=ev.severity,
                **ev.payload,
            )
    return n


# The individual pipeline-health checks and the rolling drift metrics live in
# sibling watchdog_* modules so this module can focus on the event model,
# persistence, and run orchestration. Imported here (after WatchdogEvent and
# the SEVERITY_* constants are defined, which the sibling modules import back
# from this module) because tests and dayclose/job_runtime reference them via
# ``watchdog._name``, and because run_watchdog below resolves them through
# this module's globals, which keeps monkeypatching on watchdog effective.
from wnba_oracle.scheduler.watchdog_checks import (  # noqa: E402
    ENRICHMENT_SOURCE_Q,
    FEATURE_CONTENT_Q,
    FROZEN_Q,
    LABEL_COVERAGE_Q,
    LABEL_MISSING_SAMPLE_Q,
    POOL_SIZE_Q,
    REPO_ROOT,
    _check_config_drift,
    _check_enrichment_freshness,
    _check_enrichment_source,
    _check_feature_content,
    _check_freeze,
    _check_label_coverage,
    _check_model_artifact,
    _check_opponent_reciprocity,
    _check_pool,
    _slate_freeze_deadline,
)
from wnba_oracle.scheduler.watchdog_drift import (  # noqa: E402
    DRIFT_CORR_WARN,
    DRIFT_LABELS_Q,
    DRIFT_LB_Q,
    DRIFT_MEDIAN_GAP_WARN,
    DRIFT_MIN_PICK_PAIRS,
    DRIFT_WINDOW,
    DRIFT_WINDOW_Q,
    _check_prediction_drift,
    _pearson,
    compute_drift_metrics,
)

__all__ = [
    "DRIFT_CORR_WARN",
    "DRIFT_LABELS_Q",
    "DRIFT_LB_Q",
    "DRIFT_MEDIAN_GAP_WARN",
    "DRIFT_MIN_PICK_PAIRS",
    "DRIFT_WINDOW",
    "DRIFT_WINDOW_Q",
    "ENRICHMENT_SOURCE_Q",
    "FEATURE_CONTENT_Q",
    "FROZEN_Q",
    "LABEL_COVERAGE_Q",
    "LABEL_MISSING_SAMPLE_Q",
    "POOL_SIZE_Q",
    "REPO_ROOT",
    "_check_config_drift",
    "_check_enrichment_freshness",
    "_check_enrichment_source",
    "_check_feature_content",
    "_check_freeze",
    "_check_label_coverage",
    "_check_model_artifact",
    "_check_opponent_reciprocity",
    "_check_pool",
    "_check_prediction_drift",
    "_pearson",
    "_slate_freeze_deadline",
    "compute_drift_metrics",
]


def _ping_on_critical(events: list[WatchdogEvent]) -> None:
    """D84: best-effort dead-man's-switch ping when anything critical fired.

    GETs {WATCHDOG_PING_URL}/fail so an external monitor (healthchecks.io
    style) pages the operator. Never raises; paging must not break the
    pipeline it watches. No-op until the operator provisions the URL.

    ``request_with_retry`` only raises on a transport-level failure (DNS,
    connection refused, timeout) or an exhausted-retries non-2xx response;
    a non-retryable non-2xx status (e.g. 404 from a stale/misconfigured
    monitor URL, 401 from a rotated token) is returned normally, not
    raised. Treating "no exception" as "delivered" logged a false
    watchdog_ping_sent for those responses, which is exactly the silent
    failure a dead-man's-switch exists to catch -- so the status code is
    checked explicitly instead of trusting the absence of an exception.
    """
    from wnba_oracle.common.settings import get_settings

    url = get_settings().watchdog_ping_url.strip().rstrip("/")
    if not url:
        return
    if not any(ev.severity == SEVERITY_CRITICAL for ev in events):
        return
    try:
        from oracle_core.http import HttpxSyncTransport, RetryPolicy, request_with_retry

        with HttpxSyncTransport() as transport:
            response = request_with_retry(
                transport,
                "GET",
                f"{url}/fail",
                policy=RetryPolicy(max_attempts=2, base_delay=0.25, max_delay=1.0),
                timeout=5.0,
            )
        if 200 <= response.status_code < 300:
            log.info("watchdog_ping_sent", url_suffix="/fail")
        else:
            log.warning(
                "watchdog_ping_not_delivered",
                url_suffix="/fail",
                status_code=response.status_code,
            )
    except Exception as exc:
        log.warning("watchdog_ping_failed", error_type=type(exc).__name__)


def run_watchdog(
    slate_date: str,
    *,
    now_utc: dt.datetime | None = None,
    check_config_drift: bool = True,
) -> list[WatchdogEvent]:
    """Run all checks for the slate; persist deduplicated events.

    Returns the full event list for caller-side logging / API surface.
    Persistence is idempotent within 6h per (slate, trigger).

    ``check_config_drift`` gates the EXPECTED_PROD_CONFIG comparison. That
    config describes cron-job2's env only (see EXPECTED_PROD_CONFIG docstring);
    running it from job1's process reads job1's environment, which never has
    those job2-only optimizer/model knobs set, so every call would misreport
    them as reverted-to-default drift. Callers outside job2's own dispatch
    should pass False.
    """
    log.info("watchdog_run", slate_date=slate_date)
    events: list[WatchdogEvent] = []
    events.extend(_check_pool(slate_date))
    events.extend(_check_enrichment_freshness(slate_date, now_utc=now_utc))
    events.extend(_check_enrichment_source(slate_date))
    events.extend(_check_opponent_reciprocity(slate_date))
    events.extend(_check_freeze(slate_date, now_utc=now_utc))
    events.extend(_check_model_artifact(slate_date))
    events.extend(_check_feature_content(slate_date))
    if check_config_drift:
        events.extend(_check_config_drift(slate_date))
    if events:
        persist_events(events)
        _ping_on_critical(events)
    else:
        log.info("watchdog_clean", slate_date=slate_date)
    return events
