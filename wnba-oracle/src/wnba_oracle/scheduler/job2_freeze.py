"""Job 2 freeze persistence: append-only frozen_lineups writes.

Extracted from job2.py. Owns the FROZEN_* SQL, the Redis freeze locks,
the per-player payload materialization, and the idempotent append. The
freeze contract (one lineup per slate, never re-rolled underneath the
operator, D82 append-only history) lives here; job2.run decides WHEN to
freeze and this module decides HOW.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from oracle_core.storage import Lease, RedisLeaseStore
from sqlalchemy import text

from wnba_oracle.common.logging import get_logger
from wnba_oracle.db.engine import get_engine, get_redis
from wnba_oracle.picker.optimize import LineupRecommendation

log = get_logger("oracle.job2")

# D82: frozen_lineups is append-only. Every freeze fire (the first tip-relative T-40 fire
# freeze and D75 late re-freeze alike) inserts a NEW row with the next
# freeze_seq for (slate_date, model_sha); nothing ever updates a frozen row
# in place, so the lineup the operator saw at any point stays reconstructable.
# The seq is computed in the INSERT's source SELECT; if two writers race to
# the same seq the unique constraint on (slate_date, model_sha, freeze_seq)
# turns the loser into a clean no-op (empty RETURNING) that _freeze retries.
#
# :model_sha is CAST to varchar explicitly. It is referenced twice (the SELECT
# value and the WHERE filter); after migration 0008 widened the column to
# varchar(64), Postgres deduced inconsistent types for the reused bind param
# ("text versus character varying") and raised AmbiguousParameter on every
# append, which silently blocked all freezes from 2026-06-13 onward. The cast
# pins a single type so the parameter unifies.
FROZEN_APPEND = text(
    """
    INSERT INTO frozen_lineups (
        slate_date, model_sha, payout_regime, frozen_at, lineup,
        entry_recommendation, expected_payout, metadata_json,
        freeze_seq, frozen_via, operation_key
    )
    SELECT
        :slate_date, CAST(:model_sha AS varchar), :payout_regime, now(),
        CAST(:lineup AS JSONB),
        :entry_recommendation, :expected_payout, CAST(:metadata_json AS JSONB),
        COALESCE(MAX(freeze_seq), 0) + 1, :frozen_via, :operation_key
    FROM frozen_lineups
    WHERE slate_date = :slate_date AND model_sha = CAST(:model_sha AS varchar)
    ON CONFLICT DO NOTHING
    RETURNING id, freeze_seq;
    """
)

FROZEN_EXISTS = text("SELECT 1 FROM frozen_lineups WHERE slate_date = :sd AND model_sha = :ms")
FROZEN_OPERATION_EXISTS = text(
    "SELECT 1 FROM frozen_lineups "
    "WHERE slate_date = :sd AND model_sha = :ms AND operation_key = :operation_key"
)

FREEZE_LEASE_TTL_SECONDS = 24 * 3600


def _build_per_player(
    rec: LineupRecommendation,
    projection_by_pid: dict[int, dict],
) -> list[dict]:
    """Materialize the per-player projection list embedded in the frozen
    lineup JSONB. The frontend's FrozenLineup contract reads this to
    render player names, teams, opponents, positions, boosts, and the
    minutes-quantile interval bar.

    Minutes P10/P50/P90 pass through from the predictor (the same
    project_minutes_from_base + minutes_vol the D55/D63 tiers use to score
    the player). Rows without a projection map (missing pid, upstream
    bug) fall back to a rank-aware default so the row still emits with
    a plausible interval instead of crashing the freeze.
    """
    pid_order = list(rec.player_ids)
    out: list[dict] = []
    for slot_idx, pid in enumerate(pid_order):
        proj = projection_by_pid.get(int(pid), {})
        # Rank-aware minutes fallback used only when the predictor did not
        # attach an interval (safe-default path -- missing pid or a tier that
        # skipped minutes projection). Slot 1 leans starter, slot 5 trails.
        p50_default = max(22.0, 32.0 - 1.5 * slot_idx)
        p10m = float(proj.get("pred_minutes_p10", p50_default - 4.0))
        p50m = float(proj.get("pred_minutes_p50", p50_default))
        p90m = float(proj.get("pred_minutes_p90", p50_default + 4.0))
        entry = {
            "player_id": int(pid),
            "display_name": proj.get("display_name", f"Player {pid}"),
            "team": proj.get("team", ""),
            "opponent": proj.get("opponent", ""),
            "position": proj.get("position", "F"),
            "card_boost": float(proj.get("card_boost", 0.0)),
            "pred_real_score_p50": float(proj.get("pred_real_score_p50", 0.0)),
            "pred_minutes_p10": p10m,
            "pred_minutes_p50": p50m,
            "pred_minutes_p90": p90m,
        }
        if proj.get("game_id"):
            entry["game_id"] = str(proj["game_id"])
        # D69 / Phase 2b: pass through the real_score interval when the
        # trained heads served this player. Absent fields are backward-compatible.
        if "pred_real_score_p10" in proj:
            entry["pred_real_score_p10"] = float(proj["pred_real_score_p10"])
            entry["pred_real_score_p90"] = float(proj["pred_real_score_p90"])
        # D105: archetype label (metadata-only; does not affect predictions).
        if "archetype" in proj:
            entry["archetype"] = proj["archetype"]
        if "streak_driver" in proj:
            entry["streak_driver"] = proj["streak_driver"]
            entry["streak_quality"] = float(proj.get("streak_quality", 0.0))
        if "stat_leverage" in proj:
            entry["stat_leverage"] = float(proj["stat_leverage"])
        out.append(entry)
    return out


def _release_freeze_lock(slate_date: str, force: bool, owner_token: str | None) -> None:
    """Drop the Redis freeze lock for a slate so the next fire can retry.

    The lock (wnba.frozen.{sd} / wnba.late_frozen.{sd}) is taken with a 24h
    TTL before the Postgres append. If the append then fails, leaving the lock
    set would defer every later fire for the full TTL and wedge the slate (the
    2026-06-13 outage). Releasing it on failure makes the lock self-healing:
    a transient append error costs one fire, not a day. Best-effort; a Redis
    error here is irrelevant because the lock auto-expires anyway.
    """
    if not owner_token:
        return
    key = f"wnba.late_frozen.{slate_date}" if force else f"wnba.frozen.{slate_date}"
    try:
        RedisLeaseStore(get_redis(), prefix="").release(Lease(key=key, token=owner_token))
    except Exception as exc:
        log.warning("job2_freeze_lock_release_failed", slate_date=slate_date, error=str(exc)[:120])


def _freeze(
    slate_date: str,
    model_sha: str,
    rec: LineupRecommendation,
    payout_regime: str,
    projection_by_pid: dict[int, dict],
    *,
    force: bool = False,
    payout_curve: dict | None = None,
    serving_knobs: dict | None = None,
    model_provenance: dict | None = None,
    source_assurance: dict | None = None,
    via: str | None = None,
) -> bool:
    """Idempotent freeze: first job2 fire writes, subsequent fires no-op.

    True-freeze semantics (the operator submits one lineup per slate and
    must not see it change underneath them):

    1. Check Postgres for an existing row keyed on (slate_date, model_sha).
       Existence is the canonical "already frozen" signal -- Redis is just
       a fast-path hint.
    2. If absent, take the Redis SETNX lock as a fast soft-lock to
       discourage concurrent inserts within the cron window (cron-job2
       fires every 15 min; without the lock two cron tasks could race
       between the existence-check and the INSERT). On lock-miss treat
       it as "another fire is in flight" and bail without writing.
    3. Issue FROZEN_APPEND (D82): an INSERT that computes the next
       freeze_seq for the key and no-ops on a seq collision. ``RETURNING``
       distinguishes "I wrote this row" from "lost the seq race".

    When force=True (late re-freeze, D75): skip the Postgres existence
    check, use the wnba.late_frozen.{slate_date} Redis key (first-fire-wins
    per day, 24h TTL) to prevent duplicate late re-freezes, and APPEND a
    new row (D82) so the earlier freeze stays intact for audit. This path
    is only reached when LATE_REFREEZE_ENABLED=true, the current UTC time
    is past LATE_REFREEZE_AFTER_UTC, and the D83 lock gate allows it.

    Returns True iff this invocation appended a freeze record.
    """
    eng = get_engine()
    frozen_via = via or ("job2_late_refreeze" if force else "job2_first_fire")
    operation_key = frozen_via if force else "first"
    lock_owner: str | None = None

    if force:
        # D75 late re-freeze: use a separate Redis key so only the first
        # late-fire appends. Subsequent fires (every 15 min) see the key
        # already set and bail without touching frozen_lineups.
        try:
            rd = get_redis()
            late_key = f"wnba.late_frozen.{slate_date}"
            lease = RedisLeaseStore(rd, prefix="").acquire(
                late_key,
                ttl_seconds=FREEZE_LEASE_TTL_SECONDS,
            )
            lock_owner = lease.token if lease else None
            lock_acquired = lease is not None
        except Exception as redis_exc:
            log.warning("job2_redis_unavailable", error=str(redis_exc)[:120])
            lock_owner = None
            lock_acquired = True  # proceed; Postgres UPSERT is the canonical guard
        if not lock_acquired:
            log.info("job2_late_refreeze_already_done", slate_date=slate_date)
            return False
    else:
        with eng.connect() as conn:
            existing = conn.execute(FROZEN_EXISTS, {"sd": slate_date, "ms": model_sha}).first()
        if existing:
            log.info("job2_already_frozen", slate_date=slate_date, model_sha=model_sha)
            return False

        try:
            rd = get_redis()
            key = f"wnba.frozen.{slate_date}"
            # The 24h TTL covers a full slate window; if the writer crashes the
            # lock auto-releases for the next fire to retry.
            lease = RedisLeaseStore(rd, prefix="").acquire(
                key,
                ttl_seconds=FREEZE_LEASE_TTL_SECONDS,
            )
            lock_owner = lease.token if lease else None
            lock_acquired = lease is not None
        except Exception as redis_exc:
            log.warning("job2_redis_unavailable", error=str(redis_exc)[:120])
            lock_owner = None
            lock_acquired = True  # proceed; Postgres ON CONFLICT guards correctness
        if not lock_acquired:
            log.info(
                "job2_freeze_lock_held",
                slate_date=slate_date,
                note="another job2 fire is mid-freeze; deferring",
            )
            return False

    # D90 calibration fields: payout_curve + serving_knobs persist in the
    # lineup JSONB so the placement reader can join the freeze-time forecast
    # to the realized contest outcome. None payloads are dropped to keep the
    # JSONB compact when callers (older test fixtures) do not supply them.
    lineup_payload: dict = {
        "player_ids": list(rec.player_ids),
        "slot_multipliers": list(rec.slot_multipliers),
        "lineup_score_p10": rec.lineup_score_p10,
        "lineup_score_p50": rec.lineup_score_p50,
        "lineup_score_p90": rec.lineup_score_p90,
        "per_player": _build_per_player(rec, projection_by_pid),
    }
    if payout_curve is not None:
        lineup_payload["payout_curve"] = payout_curve
    if serving_knobs is not None:
        lineup_payload["serving_knobs"] = serving_knobs
    if rec.stacking_decision is not None:
        lineup_payload["stack_decision"] = asdict(rec.stacking_decision)
    if model_provenance is not None:
        lineup_payload["model_provenance"] = model_provenance
    if source_assurance is not None:
        lineup_payload["source_assurance"] = source_assurance

    payload = {
        "slate_date": slate_date,
        "model_sha": model_sha,
        "payout_regime": payout_regime,
        "lineup": json.dumps(lineup_payload),
        "entry_recommendation": rec.entry_flag,
        "expected_payout": rec.expected_payout,
        # frozen_via stays duplicated in metadata_json for one release so
        # existing readers of metadata keep working (drop after frontend
        # confirms it reads the column).
        "metadata_json": json.dumps({"frozen_via": frozen_via}),
        "frozen_via": frozen_via,
        "operation_key": operation_key,
    }
    # One retry on an empty RETURNING: a concurrent appender took our seq.
    # The Redis locks make this near-impossible, but the constraint is the
    # actual correctness boundary, so honor it.
    result = None
    try:
        for attempt in (1, 2):
            with eng.begin() as conn:
                result = conn.execute(FROZEN_APPEND, payload).first()
            if result is not None:
                break
            with eng.connect() as conn:
                duplicate = conn.execute(
                    FROZEN_OPERATION_EXISTS,
                    {"sd": slate_date, "ms": model_sha, "operation_key": operation_key},
                ).first()
            if duplicate:
                log.info(
                    "job2_freeze_operation_already_committed",
                    slate_date=slate_date,
                    operation_key=operation_key,
                )
                return False
            log.info("job2_lost_seq_race", slate_date=slate_date, attempt=attempt)
    except Exception as append_exc:
        # The append raised (e.g. a SQL/parameter error). Release the freeze
        # lock so the next fire retries immediately instead of deferring for
        # the 24h TTL, then surface the error to the caller.
        _release_freeze_lock(slate_date, force, lock_owner)
        log.exception(
            "job2_freeze_append_error", slate_date=slate_date, error=str(append_exc)[:200]
        )
        raise RuntimeError("failed to append frozen lineup") from append_exc
    if result is None:
        _release_freeze_lock(slate_date, force, lock_owner)
        log.warning("job2_freeze_append_failed", slate_date=slate_date, via=frozen_via)
        raise RuntimeError("freeze append lost its sequence race twice")
    log.info(
        "job2_late_refrozen" if force else "job2_frozen",
        slate_date=slate_date,
        row_id=int(result[0]),
        freeze_seq=int(result[1]),
    )
    return True
