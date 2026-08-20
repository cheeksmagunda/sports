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
from pathlib import Path

from sqlalchemy import text

from wnba_oracle.common.logging import get_logger
from wnba_oracle.db.engine import get_engine

REPO_ROOT = Path(__file__).resolve().parents[3]

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


# Per-check SQL kept here (not embedded in the run loop) for grep-ability.

POOL_SIZE_Q = text(
    "SELECT COUNT(*)::int AS n, COUNT(DISTINCT team)::int AS n_teams, "
    "MAX(captured_at) AS last_captured "
    "FROM job1_enrichment WHERE slate_date = :sd"
)

FROZEN_Q = text(
    "SELECT lineup, expected_payout, frozen_at "
    "FROM frozen_lineups "
    "WHERE slate_date = :sd "
    "ORDER BY frozen_at DESC, id DESC LIMIT 1"
)


def _check_pool(slate_date: str) -> list[WatchdogEvent]:
    eng = get_engine()
    with eng.connect() as conn:
        row = conn.execute(POOL_SIZE_Q, {"sd": slate_date}).first()
    n = int(row[0]) if row and row[0] is not None else 0
    n_teams = int(row[1]) if row and row[1] is not None else 0
    if n == 0:
        return [
            WatchdogEvent(
                slate_date=slate_date,
                trigger="no_job1_pool",
                severity=SEVERITY_CRITICAL,
                payload={"pool_size": 0},
            )
        ]
    out: list[WatchdogEvent] = []
    if n < 10:
        # D84: escalated from warn. A sub-10 pool means the ingest
        # partially failed and the tip-relative (T-40) freeze would optimize over a
        # broken universe (the 2026-06-08 incident shape).
        out.append(
            WatchdogEvent(
                slate_date=slate_date,
                trigger="pool_too_small",
                severity=SEVERITY_ERROR,
                payload={"pool_size": n, "threshold": 10},
            )
        )
    if n_teams < 2:
        # Rows exist but from a single team: a degenerate capture that a
        # raw row count can miss. No valid slate has one team.
        out.append(
            WatchdogEvent(
                slate_date=slate_date,
                trigger="pool_degenerate_teams",
                severity=SEVERITY_CRITICAL,
                payload={"pool_size": n, "n_teams": n_teams},
            )
        )
    return out


def _check_enrichment_freshness(
    slate_date: str, *, now_utc: dt.datetime | None = None
) -> list[WatchdogEvent]:
    """D84: warn when the slate's enrichment is stale near freeze time.

    After 20:00 UTC (an hour before the legacy 21:00 evening freeze) the
    newest job1_enrichment capture should be from today's 13:00 UTC fire or
    later. An older capture means job1 silently never refreshed and job2
    is about to freeze on yesterday's universe.

    The 20:00 UTC gate assumes an evening slate. An early tip-off (first
    tip before ~17:00 UTC, D93 tip-relative freeze) already froze hours
    before this check ever runs, on whatever was fresh at that time --
    checking against a fixed 13:30 UTC floor at 20:00 UTC is a guaranteed
    false positive for those slates. Skip once a lineup is already frozen;
    the freeze already happened on today's universe by definition.
    """
    now_utc = now_utc or dt.datetime.now(dt.UTC)
    if now_utc.strftime("%Y-%m-%d") != slate_date or now_utc.hour < 20:
        return []
    eng = get_engine()
    with eng.connect() as conn:
        if conn.execute(FROZEN_Q, {"sd": slate_date}).first() is not None:
            return []
        row = conn.execute(POOL_SIZE_Q, {"sd": slate_date}).first()
    last_captured = row[2] if row else None
    if last_captured is None:
        return []  # no_job1_pool already covers the empty case
    if last_captured.tzinfo is None:
        last_captured = last_captured.replace(tzinfo=dt.UTC)
    fresh_floor = now_utc.replace(hour=13, minute=30, second=0, microsecond=0)
    if last_captured >= fresh_floor:
        return []
    return [
        WatchdogEvent(
            slate_date=slate_date,
            trigger="enrichment_stale",
            severity=SEVERITY_WARN,
            payload={
                "last_captured_utc": last_captured.isoformat(),
                "fresh_floor_utc": fresh_floor.isoformat(),
            },
        )
    ]


# Coverage universe: players referenced by the captured top-20 leaderboard
# lineups. They provably participated in the contest, so a missing label is
# always an ingestion gap, never noise. The job1_enrichment pool cannot be
# the universe -- it is structurally ~3x wider than contest label coverage
# (pool ~90 vs labels ~30 on a 3-game slate), so comparing against it fired
# a false ERROR on every healthy day. slate_date is VARCHAR on both tables
# here; cast the shared :sd param explicitly so Postgres types it.
LABEL_COVERAGE_Q = text(
    """
    WITH lb_players AS (
        SELECT DISTINCT (p->>'playerId')::int AS pid
        FROM contest_leaderboards cl,
             jsonb_array_elements(cl.lineup) p
        WHERE cl.slate_date = CAST(:sd AS varchar)
    )
    SELECT
        (SELECT COUNT(*)::int FROM lb_players) AS n_contest,
        (SELECT COUNT(*)::int FROM lb_players lp
         WHERE NOT EXISTS (
             SELECT 1 FROM slate_labels l
             WHERE l.slate_date = CAST(:sd AS varchar)
               AND l.platform_player_id = lp.pid
         )) AS n_missing
    """
)

LABEL_MISSING_SAMPLE_Q = text(
    """
    SELECT DISTINCT (p->>'playerId')::int AS pid,
           MAX(p->>'displayName') AS name
    FROM contest_leaderboards cl,
         jsonb_array_elements(cl.lineup) p
    WHERE cl.slate_date = CAST(:sd AS varchar)
      AND NOT EXISTS (
          SELECT 1 FROM slate_labels l
          WHERE l.slate_date = CAST(:sd AS varchar)
            AND l.platform_player_id = (p->>'playerId')::int
      )
    GROUP BY (p->>'playerId')::int
    ORDER BY pid
    LIMIT 10
    """
)


def _check_label_coverage(slate_date: str) -> list[WatchdogEvent]:
    """D85: contest players missing from slate_labels lose training labels
    permanently (the Loyd/Boston gap on 2026-06-08).

    Compares the players referenced by the captured top-20 leaderboard
    lineups against slate_labels after dayclose finalizes the contest.
    Any gap in that set is a real ingestion failure: error above 20%
    missing, warn on any gap. Called from the dayclose path, not the cron
    loop: labels and leaderboards only exist after contest finalization.
    """
    eng = get_engine()
    with eng.connect() as conn:
        row = conn.execute(LABEL_COVERAGE_Q, {"sd": slate_date}).first()
        n_contest = int(row[0]) if row and row[0] is not None else 0
        n_missing = int(row[1]) if row and row[1] is not None else 0
        if n_contest == 0 or n_missing == 0:
            return []
        sample = [
            {"player_id": int(r[0]), "name": str(r[1])}
            for r in conn.execute(LABEL_MISSING_SAMPLE_Q, {"sd": slate_date})
        ]
    frac = n_missing / n_contest
    return [
        WatchdogEvent(
            slate_date=slate_date,
            trigger="label_coverage_gap",
            severity=SEVERITY_ERROR if frac > 0.20 else SEVERITY_WARN,
            payload={
                "n_contest": n_contest,
                "n_missing": n_missing,
                "missing_frac": round(frac, 3),
                "sample": sample,
            },
        )
    ]


# Rolling drift metrics (dayclose only). Reads the last N *finalized* slates
# and reports (a) Pearson correlation between per-pick freeze-time pred_p50
# and realized real_score, and (b) rolling median gap between our lineup
# score and the top-20 median. Baselines from D77 walk-forward + the
# 2026-07-03 loss-ledger snapshot; alert only on materially worse than
# baseline (silent when steady-state, even though steady-state is not
# healthy -- an operator already knows).
DRIFT_WINDOW = 20
DRIFT_CORR_WARN = 0.35  # D77 walk-forward baseline was 0.554
DRIFT_MEDIAN_GAP_WARN = -25.0  # loss-ledger baseline ~-17

# 2026-08-03: the corr alert fired on 15-20 pick pairs for a month straight and
# every reading was statistically indistinguishable from both the pooled history
# (0.408 over 95 pairs) and the 0.554 baseline it was compared against. At
# r=0.285, n=20 the 95% CI is [-0.180, +0.646], which also contains zero.
#
# Minimum n to separate DRIFT_CORR_WARN from the baseline at 95%, via Fisher z:
#   atanh(0.554) - atanh(0.35) = 0.2589;  1.96 / sqrt(n - 3) <= 0.2589  =>  n >= 61
#
# DRIFT_WINDOW was 10, capping pairs at 50, so the check could never reach that
# power. Window raised to 20 (max 100 pairs) and the alert now holds fire below
# the threshold rather than reporting noise as a retrain signal.
#
# Note this correlation is taken over the five optimizer-selected picks only,
# whose predicted spread is range-restricted (sd 1.072) against a full-width
# realized spread. It is not the same estimator as the D77 full-corpus
# walk-forward figure, so 0.35 remains a rough guide, not a like-for-like bound.
DRIFT_MIN_PICK_PAIRS = 61

DRIFT_WINDOW_Q = text(
    """
    SELECT DISTINCT ON (f.slate_date)
        f.slate_date::text AS slate_date,
        f.freeze_seq,
        f.lineup
    FROM frozen_lineups f
    WHERE EXISTS (
        SELECT 1 FROM contest_leaderboards cl
        WHERE cl.slate_date = f.slate_date::text
    )
    AND EXISTS (
        SELECT 1 FROM slate_labels l
        WHERE l.slate_date = f.slate_date::text
          AND l.real_score IS NOT NULL
    )
    ORDER BY f.slate_date DESC, f.frozen_at DESC, f.id DESC
    LIMIT :n
    """
)

DRIFT_LABELS_Q = text(
    """
    SELECT platform_player_id, real_score, card_boost
    FROM slate_labels
    WHERE slate_date = :sd AND real_score IS NOT NULL
    """
)

DRIFT_LB_Q = text(
    "SELECT score FROM contest_leaderboards WHERE slate_date = :sd ORDER BY rank ASC LIMIT 20"
)


def _pearson(pairs: list[tuple[float, float]]) -> float | None:
    """Pearson correlation over (x, y) pairs. Returns None when the sample
    is degenerate (n<3) or either variable has zero variance."""
    n = len(pairs)
    if n < 3:
        return None
    mean_x = sum(p[0] for p in pairs) / n
    mean_y = sum(p[1] for p in pairs) / n
    num = sum((p[0] - mean_x) * (p[1] - mean_y) for p in pairs)
    denom_x = sum((p[0] - mean_x) ** 2 for p in pairs)
    denom_y = sum((p[1] - mean_y) ** 2 for p in pairs)
    if denom_x <= 0 or denom_y <= 0:
        return None
    return num / (denom_x * denom_y) ** 0.5


def compute_drift_metrics(
    window: int = DRIFT_WINDOW,
) -> dict[str, float | int | None] | None:
    """Read the last ``window`` finalized slates and return calibration
    metrics. Pure(-ish) helper: no clock, no logging, no emit -- unit-testable
    over a live engine. Returns None when fewer than 3 slates qualify."""
    eng = get_engine()
    with eng.connect() as conn:
        rows = conn.execute(DRIFT_WINDOW_Q, {"n": window}).fetchall()
        if len(rows) < 3:
            return None

        pick_pairs: list[tuple[float, float]] = []
        score_gaps: list[float] = []
        n_slates_scored = 0
        n_lb_missing = 0

        for row in rows:
            sd = row.slate_date
            lu = row.lineup
            lu = lu if isinstance(lu, dict) else json.loads(lu)
            pids: list[int] = [int(x) for x in (lu.get("player_ids") or [])]
            per = lu.get("per_player") or []
            if not pids or not per:
                continue
            pred_by_pid: dict[int, float] = {}
            for entry in per:
                try:
                    pred_by_pid[int(entry["player_id"])] = float(
                        entry.get("pred_real_score_p50") or 0.0
                    )
                except (KeyError, TypeError, ValueError):
                    continue

            labels = {
                int(r._mapping["platform_player_id"]): (
                    float(r._mapping["real_score"] or 0.0),
                    float(r._mapping["card_boost"] or 0.0),
                )
                for r in conn.execute(DRIFT_LABELS_Q, {"sd": sd}).fetchall()
            }
            for pid, pred in pred_by_pid.items():
                if pid in labels:
                    pick_pairs.append((pred, labels[pid][0]))

            # Per-slate gap vs top-20 median.
            all_pids_scored = all(pid in labels for pid in pids)
            if not all_pids_scored:
                continue
            picks = [(pid, labels[pid][1], labels[pid][0]) for pid in pids]
            picks.sort(key=lambda x: x[2], reverse=True)
            slots = [2.0, 1.8, 1.6, 1.4, 1.2]
            our_score = sum(rs * (boost + slots[i]) for i, (_, boost, rs) in enumerate(picks))

            lb_rows = conn.execute(DRIFT_LB_Q, {"sd": sd}).fetchall()
            if not lb_rows:
                n_lb_missing += 1
                continue
            lb_scores = sorted(float(r._mapping["score"]) for r in lb_rows)
            median = lb_scores[len(lb_scores) // 2]
            score_gaps.append(our_score - median)
            n_slates_scored += 1

    if n_slates_scored < 3:
        return None
    score_gaps_sorted = sorted(score_gaps)
    median_gap = score_gaps_sorted[len(score_gaps_sorted) // 2]
    return {
        "n_slates": n_slates_scored,
        "n_pick_pairs": len(pick_pairs),
        "pick_pred_vs_real_corr": _pearson(pick_pairs),
        "median_score_gap": median_gap,
        "worst_score_gap": min(score_gaps),
        "best_score_gap": max(score_gaps),
    }


def _check_prediction_drift(slate_date: str, *, window: int = DRIFT_WINDOW) -> list[WatchdogEvent]:
    """Rolling-window calibration alert (dayclose-only).

    Fires when either signal materially worsens:
    - Pearson corr(pred_p50, realized rs) across our five picks over the
      window drops below DRIFT_CORR_WARN. D77 walk-forward baseline was
      0.554; sub-0.35 is a 30%+ degradation.
    - Rolling median (our_score - top20_median) drops below
      DRIFT_MEDIAN_GAP_WARN. The 2026-07-03 loss-ledger baseline sat at
      ~-17; sub-25 means the lineup got materially worse.

    Steady-state under baseline does NOT fire -- the operator already
    knows the state from the loss ledger. Fires only on regression from
    baseline.
    """
    try:
        m = compute_drift_metrics(window=window)
    except Exception as exc:
        log.warning("drift_check_failed", reason=str(exc)[:120])
        return []
    if not m:
        return []
    events: list[WatchdogEvent] = []
    corr = m.get("pick_pred_vs_real_corr")
    n_pairs = int(m.get("n_pick_pairs") or 0)
    if corr is not None and float(corr) < DRIFT_CORR_WARN:
        if n_pairs < DRIFT_MIN_PICK_PAIRS:
            log.info(
                "drift_corr_underpowered",
                n_pick_pairs=n_pairs,
                min_pairs=DRIFT_MIN_PICK_PAIRS,
                corr=round(float(corr), 3),
            )
        else:
            events.append(
                WatchdogEvent(
                    slate_date=slate_date,
                    trigger="prediction_calibration_drift",
                    severity=SEVERITY_WARN,
                    payload={
                        "window": m["n_slates"],
                        "n_pick_pairs": n_pairs,
                        "corr": round(float(corr), 3),
                        "threshold": DRIFT_CORR_WARN,
                        "baseline_d77": 0.554,
                        "note": (
                            "Rolling Pearson corr(pred_p50, realized) over the five "
                            "picks has dropped below the D77-baseline threshold on a "
                            "sample large enough to separate the two; retrain candidate. "
                            "Range-restricted estimator, not like-for-like with D77."
                        ),
                    },
                )
            )
    gap = m.get("median_score_gap")
    if gap is not None and float(gap) < DRIFT_MEDIAN_GAP_WARN:
        events.append(
            WatchdogEvent(
                slate_date=slate_date,
                trigger="lineup_gap_regression",
                severity=SEVERITY_WARN,
                payload={
                    "window": m["n_slates"],
                    "median_gap": round(float(gap), 2),
                    "worst_gap": round(float(m["worst_score_gap"] or 0.0), 2),
                    "threshold": DRIFT_MEDIAN_GAP_WARN,
                    "baseline_ledger_2026_07_03": -17.0,
                    "note": (
                        "10-slate median (our_score - top20_median) has "
                        "worsened past the 2026-07-03 loss-ledger baseline."
                    ),
                },
            )
        )
    log.info(
        "drift_metrics",
        window=m["n_slates"],
        corr=m.get("pick_pred_vs_real_corr"),
        median_gap=m.get("median_score_gap"),
    )
    return events


def _ping_on_critical(events: list[WatchdogEvent]) -> None:
    """D84: best-effort dead-man's-switch ping when anything critical fired.

    GETs {WATCHDOG_PING_URL}/fail so an external monitor (healthchecks.io
    style) pages the operator. Never raises; paging must not break the
    pipeline it watches. No-op until the operator provisions the URL.
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
            request_with_retry(
                transport,
                "GET",
                f"{url}/fail",
                policy=RetryPolicy(max_attempts=2, base_delay=0.25, max_delay=1.0),
                timeout=5.0,
            )
        log.info("watchdog_ping_sent", url_suffix="/fail")
    except Exception as exc:
        log.warning("watchdog_ping_failed", error_type=type(exc).__name__)


def _slate_freeze_deadline(slate_date: str, settings: object) -> dt.datetime | None:
    """The tip-relative freeze deadline (first_tip - freeze_lead_minutes) for a
    slate, or None when slate_meta has no tip time. Best-effort; a failure
    degrades the freeze check to its static 22:00 UTC fallback."""
    try:
        from wnba_oracle.scheduler.job2 import _freeze_deadline_utc, _load_slate_lock_time

        return _freeze_deadline_utc(_load_slate_lock_time(slate_date), settings)
    except Exception as exc:
        log.warning("watchdog_freeze_deadline_failed", reason=str(exc)[:120])
        return None


def _check_freeze(slate_date: str, *, now_utc: dt.datetime | None = None) -> list[WatchdogEvent]:
    now_utc = now_utc or dt.datetime.now(dt.UTC)
    eng = get_engine()
    with eng.connect() as conn:
        row = conn.execute(FROZEN_Q, {"sd": slate_date}).first()
    out: list[WatchdogEvent] = []
    if row is None:
        # E: escalate relative to the slate's own tip. A static 22:00 UTC
        # threshold is blind to afternoon slates that lock before the evening
        # cron window -- those would miss the freeze entirely and stay silent
        # until 22:00. When slate_meta carries a first-tip, fire CRITICAL once
        # we pass first_tip - freeze_lead_minutes; otherwise fall back to the
        # legacy today + 22:00 UTC rule.
        from wnba_oracle.common.settings import get_settings

        deadline = _slate_freeze_deadline(slate_date, get_settings())
        if deadline is not None:
            overdue = now_utc >= deadline
            note = f"no frozen row by tip-relative deadline {deadline.isoformat()}"
        else:
            overdue = now_utc.strftime("%Y-%m-%d") == slate_date and now_utc.hour >= 22
            note = "no frozen row after 22:00 UTC (no tip time captured)"
        if overdue:
            out.append(
                WatchdogEvent(
                    slate_date=slate_date,
                    trigger="no_frozen_lineup",
                    severity=SEVERITY_CRITICAL,
                    payload={
                        "checked_at_utc": now_utc.isoformat(),
                        "freeze_deadline_utc": deadline.isoformat() if deadline else None,
                        "note": note,
                    },
                )
            )
        return out

    lineup_json = row[0]
    if isinstance(lineup_json, str):
        lineup_json = json.loads(lineup_json)
    per_player = lineup_json.get("per_player") if isinstance(lineup_json, dict) else None
    if not per_player or len(per_player) != 5:
        out.append(
            WatchdogEvent(
                slate_date=slate_date,
                trigger="missing_per_player",
                severity=SEVERITY_ERROR,
                payload={"per_player_len": len(per_player) if per_player else 0},
            )
        )

    expected_payout = row[1]
    if expected_payout is not None and float(expected_payout) <= 0.0:
        out.append(
            WatchdogEvent(
                slate_date=slate_date,
                trigger="zero_expected_payout",
                severity=SEVERITY_WARN,
                payload={"expected_payout": float(expected_payout)},
            )
        )
    return out


FEATURE_CONTENT_Q = text(
    "SELECT COUNT(*)::int AS n, "
    "COUNT(*) FILTER (WHERE (features_json->>'vegas_total')::float8 > 0)::int AS n_odds, "
    "COUNT(*) FILTER (WHERE (features_json->>'is_starter')::int = 1)::int AS n_starter "
    "FROM job1_enrichment WHERE slate_date = :sd"
)


def _check_model_artifact(
    slate_date: str,
    *,
    model_sha: str | None = None,
    models_dir: Path | None = None,
) -> list[WatchdogEvent]:
    """Critical if the trained model won't load -- the system would silently
    fall back to the boost heuristic (walk-forward corr 0.554 -> 0.246) with no
    other alert. Catches the catastrophic case where WNBA_ORACLE_MODEL_ARTIFACT_SHA
    is wiped/reset or points at a `.pkl` not shipped in the image.
    """
    if model_sha is None:
        from wnba_oracle.common.settings import get_settings

        model_sha = get_settings().model_artifact_sha
    sha = (model_sha or "").strip().lower()
    if not sha:
        return [
            WatchdogEvent(
                slate_date=slate_date,
                trigger="model_artifact_unset",
                severity=SEVERITY_CRITICAL,
                payload={"note": "WNBA_ORACLE_MODEL_ARTIFACT_SHA empty; serving heuristic"},
            )
        ]
    mdir = models_dir or (REPO_ROOT / "models")
    resolved = False
    if mdir.exists():
        for sidecar in mdir.glob("picker_*.sha256"):
            try:
                if sidecar.read_text().strip().lower() != sha:
                    continue
                artifact_path = sidecar.with_suffix(".pkl")
                if not artifact_path.exists():
                    continue
                # ``load_artifact`` verifies the bytes against the sidecar
                # before unpickling. A matching text file alone is not proof
                # that the shipped artifact is readable or safe to serve.
                from wnba_oracle.train.pipeline import PickerArtifact, load_artifact

                artifact = load_artifact(artifact_path)
                if not isinstance(artifact, PickerArtifact):
                    continue
                resolved = True
                break
            except Exception:
                continue
    if not resolved:
        return [
            WatchdogEvent(
                slate_date=slate_date,
                trigger="model_artifact_unresolved",
                severity=SEVERITY_CRITICAL,
                payload={
                    "sha": sha[:12],
                    "note": "artifact missing, checksum-invalid, or unloadable; serving heuristic",
                },
            )
        ]
    return []


def _check_feature_content(slate_date: str) -> list[WatchdogEvent]:
    """Warn when the pool is full but a whole upstream feed is empty -- the
    silent-degradation class the row-count checks miss (D100 shape). Empty odds
    drops the game-script tilt; zero RotoWire starters means lineups never
    parsed/joined (the confirmed-starter signal is dark)."""
    eng = get_engine()
    with eng.connect() as conn:
        row = conn.execute(FEATURE_CONTENT_Q, {"sd": slate_date}).first()
    n = int(row[0]) if row and row[0] is not None else 0
    if n < 10:
        return []  # tiny/empty pool is the _check_pool checks' job, not this.
    n_odds = int(row[1]) if row and row[1] is not None else 0
    n_starter = int(row[2]) if row and row[2] is not None else 0
    out: list[WatchdogEvent] = []
    if n_odds == 0:
        out.append(
            WatchdogEvent(
                slate_date=slate_date,
                trigger="odds_empty",
                severity=SEVERITY_WARN,
                payload={"pool": n, "note": "no vegas_total on any row; game-script tilt off"},
            )
        )
    if n_starter == 0:
        out.append(
            WatchdogEvent(
                slate_date=slate_date,
                trigger="rotowire_empty",
                severity=SEVERITY_WARN,
                payload={"pool": n, "note": "no is_starter flags; RotoWire scrape/join failed"},
            )
        )
    return out


ENRICHMENT_SOURCE_Q = text(
    """
    SELECT COUNT(*)::int AS n_total,
           COUNT(*) FILTER (
           WHERE features_json ? 'vegas_total'
           OR features_json ? 'minutes_l5'
           OR features_json ? 'is_starter'
       )::int AS n_live_enriched
    FROM job1_enrichment WHERE slate_date = :sd
    """
)


def _check_enrichment_source(slate_date: str) -> list[WatchdogEvent]:
    """D107 (#33): detect if enrichment was produced by --job backfill instead of
    live job1. Backfill fills only player_id/name/team, skipping vegas, rotowire,
    and minutes features. If rows exist but NONE have live-enrichment fields
    (vegas_total, minutes_l5, is_starter), the pool is useless and job2 will
    freeze on empty/heuristic data.
    """
    eng = get_engine()
    with eng.connect() as conn:
        row = conn.execute(ENRICHMENT_SOURCE_Q, {"sd": slate_date}).first()
    n_total = int(row[0]) if row and row[0] is not None else 0
    n_live = int(row[1]) if row and row[1] is not None else 0
    if n_total < 10:
        return []  # tiny/empty pool is the _check_pool checks' job
    if n_live == 0:
        # All rows exist but with zero live enrichment fields: backfill-produced
        return [
            WatchdogEvent(
                slate_date=slate_date,
                trigger="enrichment_from_backfill",
                severity=SEVERITY_CRITICAL,
                payload={
                    "n_rows": n_total,
                    "note": "no vegas/rotowire/minutes fields; cron--job backfill was run instead of live job1",
                },
            )
        ]
    return []


def _check_config_drift(slate_date: str, *, settings: object | None = None) -> list[WatchdogEvent]:
    """Warn when the live serving config has drifted from the validated prod
    values (e.g. an env wipe reverted a tuned knob to its safe-off default).
    Non-fatal: a drift may be intentional, but it must not be silent."""
    if settings is None:
        from wnba_oracle.common.settings import get_settings

        settings = get_settings()
    drift = settings.config_drift()  # type: ignore[attr-defined]
    if not drift:
        return []
    return [
        WatchdogEvent(
            slate_date=slate_date,
            trigger="config_drift",
            severity=SEVERITY_WARN,
            payload={"drift": {name: {"actual": a, "expected": e} for name, a, e in drift}},
        )
    ]


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
