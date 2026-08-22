"""Job 2 database read helpers.

Extracted from job2.py so the freeze module can focus on orchestration.
Every loader degrades gracefully (empty dict / None) on DB errors so the
caller falls back to its heuristic tier instead of crashing the freeze.
Tests monkeypatch these via ``job2._name``, which keeps working because
job2 re-imports them into its own namespace and its callers resolve the
names through job2's module globals.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import text

from wnba_oracle.common.logging import get_logger
from wnba_oracle.db.engine import get_engine

log = get_logger("oracle.job2")


def _load_player_history() -> dict[int, float]:
    """Per-player mean real_score from slate_labels in Postgres.

    Used as a fallback prediction tier between the EB model and the generic
    heuristic. Players not yet in the EB model (trained before their 2026 data
    was backfilled) but with any corpus history get their actual observed mean
    rather than the boost-level heuristic. This matters most for boost-3
    players: the heuristic gives them 1.81, but a player like Milic whose only
    observed slate scored 0.51 should not be treated as average-for-boost-3.

    Returns an empty dict on any read/parse error so the caller degrades
    gracefully to the heuristic.
    """
    try:
        from wnba_oracle.db.reads import read_player_history

        return read_player_history()
    except Exception:
        return {}


def _load_enrichment(slate_date: str) -> list[dict]:
    eng = get_engine()
    q = text(
        "SELECT real_sports_player_id, name, team, opponent, position, "
        "card_boost, features_json "
        "FROM job1_enrichment WHERE slate_date = :sd"
    )
    with eng.connect() as conn:
        result = conn.execute(q, {"sd": slate_date})
        return [dict(row._mapping) for row in result]


def _load_assurance_capture_times(
    slate_date: str,
) -> tuple[dict[int, dt.datetime | None], str | None]:
    """Read observation timestamps without changing model-ingress rows.

    This query is deliberately separate from ``_load_enrichment``. Production
    scoring retains the incumbent projection, row order, and row values while
    the assurance manifest receives timestamps through copied rows only.
    Failures are reduced to their exception type so credentials and connection
    details cannot enter logs or a durable recommendation.
    """

    try:
        eng = get_engine()
        q = text(
            "SELECT real_sports_player_id, captured_at FROM job1_enrichment WHERE slate_date = :sd"
        )
        with eng.connect() as conn:
            rows = conn.execute(q, {"sd": slate_date})
            captured = {
                int(row._mapping["real_sports_player_id"]): row._mapping.get("captured_at")
                for row in rows
            }
        return captured, None
    except Exception as exc:
        error_type = type(exc).__name__
        log.warning("source_assurance_capture_read_failed", error_type=error_type)
        return {}, error_type


def _load_prior_real_scores(slate_date: str) -> dict[int, list[float]]:
    """As-of per-player realized real_scores from slate_labels for all slates
    STRICTLY BEFORE `slate_date`, most-recent-first. Drives per-player
    sampling sigma (volatility). Empty on any DB error -> caller uses the
    calibrated default sigma. Walk-forward-safe: never reads the target slate.
    """
    try:
        eng = get_engine()
    except RuntimeError:
        return {}
    q = text(
        "SELECT platform_player_id, slate_date, MAX(real_score) AS real_score "
        "FROM slate_labels WHERE slate_date < :sd AND real_score IS NOT NULL "
        "GROUP BY platform_player_id, slate_date ORDER BY slate_date DESC"
    )
    out: dict[int, list[float]] = {}
    with eng.connect() as conn:
        for row in conn.execute(q, {"sd": slate_date}):
            m = row._mapping
            pid = m.get("platform_player_id")
            rs = m.get("real_score")
            if pid is None or rs is None:
                continue
            out.setdefault(int(pid), []).append(float(rs))
    return out


def _load_measured_drafts(slate_date: str) -> dict[int, int]:
    """Pull the most recent draftStats.drafts counts from slate_labels for
    the slate. Empty if Job 2 is firing before any contest finalized
    (typical case pregame). Job 2 then falls back to the popularity
    estimator."""
    try:
        eng = get_engine()
    except RuntimeError:
        return {}
    q = text(
        "SELECT platform_player_id, MAX(drafts) AS drafts "
        "FROM slate_labels WHERE slate_date = :sd AND drafts IS NOT NULL "
        "GROUP BY platform_player_id"
    )
    with eng.connect() as conn:
        rows = conn.execute(q, {"sd": slate_date}).fetchall()
    out: dict[int, int] = {}
    for r in rows:
        m = r._mapping
        pid = m.get("platform_player_id")
        d = m.get("drafts")
        if pid is None or d is None:
            continue
        out[int(pid)] = int(d)
    return out


def _load_slate_label_names(slate_date: str) -> dict[int, str]:
    """Pull display names from slate_labels for the slate, keyed by
    platform_player_id.

    Defense-in-depth name source for the frozen lineup (D50). The primary
    name path is `job1_enrichment.name` (Real Sports pool, D49). When that
    is empty for a player, this fallback fills it from the independently
    populated `slate_labels.display_name` so the freeze never ships a
    `Player <id>` placeholder when a real name exists anywhere in the DB.
    Empty / blank names are skipped so they never shadow the final
    `Player {pid}` fallback. Empty when Job 2 fires before any contest
    finalized (typical pregame), in which case the enrichment name stands.
    """
    try:
        eng = get_engine()
    except RuntimeError:
        return {}
    q = text(
        "SELECT DISTINCT ON (platform_player_id) platform_player_id, display_name "
        "FROM slate_labels WHERE slate_date = :sd "
        "ORDER BY platform_player_id, id DESC"
    )
    with eng.connect() as conn:
        rows = conn.execute(q, {"sd": slate_date}).fetchall()
    out: dict[int, str] = {}
    for r in rows:
        m = r._mapping
        pid = m.get("platform_player_id")
        name = str(m.get("display_name", "") or "").strip()
        if pid is None or not name:
            continue
        out[int(pid)] = name
    return out


SLATE_LOCK_Q = text("SELECT contest_lock_utc, first_tip_utc FROM slate_meta WHERE slate_date = :sd")


def _load_slate_lock_time(slate_date: str) -> dt.datetime | None:
    """The slate's contest lock time from slate_meta (D83).

    Prefers an explicit contest_lock_utc; falls back to first_tip_utc
    (DFS contests lock at first game start, and the platform exposes no
    lock timestamp). None when job1 never captured timing for the slate,
    in which case the gate uses its hard deadline instead.
    """
    try:
        eng = get_engine()
        with eng.connect() as conn:
            row = conn.execute(SLATE_LOCK_Q, {"sd": slate_date}).first()
    except Exception as exc:
        log.warning("job2_slate_lock_read_failed", reason=str(exc)[:120])
        return None
    if row is None:
        return None
    lock = row[0] or row[1]
    if lock is None:
        return None
    if lock.tzinfo is None:
        lock = lock.replace(tzinfo=dt.UTC)
    return lock.astimezone(dt.UTC)
