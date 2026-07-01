"""Day-close cron: capture yesterday's finalized WNBA contest and extend
the historical corpus by one slate.

Pipeline:
  1. Playwright-sniff the freshest contest id via discover_wnba_contest_id
     (cron container picks up the absolute max id across all sports; the
     downstream sport filter in fetch_contest_stats rejects non-WNBA ids).
  2. Walk backward from (max_id - 1) over a small bounded window, calling
     the existing historical backfill. The UPSERT semantics on
     slate_labels / contest_leaderboards mean re-processing an already-
     captured contest is a cheap no-op, so the window can overlap day-
     to-day without drift.
  3. Labels + leaderboards are written to Postgres (the canonical store).

Cron schedule: `0 6 * * *` UTC = 01:00 EST / 02:00 EDT = ~1h after the
latest plausible WNBA contest finalization. Contest 1831 (slate
2026-05-25) was processedAt 2026-05-26T05:07Z, so 06:00 UTC is the
earliest fire time that always catches the prior night.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os

from wnba_oracle.common.logging import get_logger
from wnba_oracle.common.settings import get_settings
from wnba_oracle.ingest.backfill import run_historical_backfill
from wnba_oracle.ingest.realsports import discover_wnba_contest_id
from wnba_oracle.picker.optimize import DEFAULT_SLOT_MULTIPLIERS

log = get_logger("oracle.dayclose")

DEFAULT_WALK_WINDOW = 12  # cover yesterday + the prior day's residue


def _auto_record_placement(slate_date: str) -> None:
    """Score yesterday's frozen lineup against the captured leaderboard and
    append a row to contest_placements. Entry count is not stored (we only
    have the top-20 capture, not the full field size), so finish_percentile
    is NULL until the operator supplies the real total via the CLI. This
    still records the lineup score, relative rank in the top-20, and the
    freeze snapshot for calibration purposes.
    """
    import json as _json

    import polars as _pl
    from sqlalchemy import create_engine, text

    from wnba_oracle.db.reads import read_leaderboards, read_slate_labels
    from wnba_oracle.scheduler.placements import auto_record_from_dayclose

    settings = get_settings()
    if not settings.database_url:
        return

    sl = read_slate_labels().filter(_pl.col("slate_date") == slate_date)
    lb = read_leaderboards().filter(_pl.col("slate_date") == slate_date)
    if sl.height == 0 or lb.height == 0:
        log.info("auto_placement_no_data", slate_date=slate_date)
        return

    # Build real-score lookup from finalized slate_labels
    rs_by_pid: dict[int, float] = {}
    boost_by_pid: dict[int, float] = {}
    for r in sl.iter_rows(named=True):
        pid = int(r["platform_player_id"])
        rs = r["real_score"]
        rs_by_pid[pid] = float(rs) if rs is not None else 0.0
        boost_by_pid[pid] = float(r["card_boost"])

    engine = create_engine(settings.database_url, future=True)
    with engine.connect() as conn:
        # Pull the most-recent frozen lineup for this slate
        row = conn.execute(
            text(
                "SELECT lineup FROM frozen_lineups WHERE slate_date = :sd ORDER BY id DESC LIMIT 1"
            ),
            {"sd": slate_date},
        ).first()
        if row is None:
            log.info("auto_placement_no_frozen_lineup", slate_date=slate_date)
            return

        lineup_json = row[0] if isinstance(row[0], dict) else _json.loads(row[0])
        player_ids = [int(p) for p in lineup_json.get("player_ids", [])]
        if not player_ids:
            return

        # Compute our realized lineup score via rearrangement
        members = sorted(
            ((pid, rs_by_pid.get(pid, 0.0)) for pid in player_ids),
            key=lambda x: -x[1],
        )
        our_score = sum(
            (DEFAULT_SLOT_MULTIPLIERS[i] + boost_by_pid.get(pid, 0.0)) * rs
            for i, (pid, rs) in enumerate(members)
        )

        lb_scores = lb["score"].to_list()
        contest_ids = lb["contest_id"].unique().to_list()
        contest_id = int(contest_ids[0]) if contest_ids else 0

        # num_brawlers is the full contest entry count (the field-size
        # denominator); it is persisted per leaderboard row and identical
        # across them. max() ignores any nulls. With it, finish_percentile
        # auto-populates exactly on slates where our entry cracked the
        # captured top-20 (see scheduler/placements.auto_record_from_dayclose).
        field_size: int | None = None
        if "num_brawlers" in lb.columns:
            nb = lb["num_brawlers"].max()
            if isinstance(nb, (int, float)):
                field_size = int(nb)

        actual_own: dict[int, float] | None = None
        total_drafts = sum(r["drafts"] or 0 for r in sl.iter_rows(named=True) if r.get("drafts"))
        if total_drafts > 0:
            actual_own = {
                int(r["platform_player_id"]): float(r["drafts"] or 0) / total_drafts
                for r in sl.iter_rows(named=True)
            }

        result = auto_record_from_dayclose(
            conn,
            slate_date=slate_date,
            entry_score=our_score,
            leaderboard_scores=lb_scores,
            contest_id=contest_id,
            actual_ownership=actual_own,
            field_size=field_size,
        )
        if result is None:
            log.info("auto_placement_skipped", slate_date=slate_date, reason="no_frozen_lineup")
        else:
            log.info(
                "auto_placement_recorded",
                slate_date=slate_date,
                our_score=round(our_score, 3),
                relative_rank=result.get("entry_rank"),
                n_lb_entries=len(lb_scores),
            )
        conn.commit()


def _cleanup_append_only_tables(retention_days: int = 14) -> None:
    """Clean up append-only tables to prevent indefinite growth (D102 item 32a).

    watchdog_events: truncate rows older than retention_days.
    frozen_lineups: keep only the max freeze_seq per slate (the serving row);
        delete stale freeze attempts that the live path never reads.
    """
    from sqlalchemy import create_engine, text

    settings = get_settings()
    if not settings.database_url:
        return

    cutoff_date = (dt.date.today() - dt.timedelta(days=retention_days)).isoformat()
    engine = create_engine(settings.database_url, future=True)
    try:
        with engine.connect() as conn:
            # Truncate old watchdog_events
            result = conn.execute(
                text("DELETE FROM watchdog_events WHERE slate_date < :cutoff"),
                {"cutoff": cutoff_date},
            )
            n_watchdog = result.rowcount or 0

            # Keep only the max freeze_seq per slate in frozen_lineups.
            # This preserves the serving row (what job2 shows) and audit history
            # (all rows via max(freeze_seq)) while deleting stale mid-slate freezes.
            result = conn.execute(
                text(
                    """DELETE FROM frozen_lineups f
					WHERE id NOT IN (
						SELECT MAX(id) FROM frozen_lineups
						GROUP BY slate_date, model_sha
					)"""
                )
            )
            n_frozen = result.rowcount or 0
            conn.commit()
            log.info(
                "dayclose_retention_cleanup",
                watchdog_old_days=retention_days,
                watchdog_deleted=n_watchdog,
                frozen_stale_deleted=n_frozen,
            )
    except Exception as exc:
        log.exception("dayclose_retention_cleanup_failed", error=str(exc))


def main() -> int:
    settings = get_settings()
    walk_window = int(os.environ.get("WNBA_DAYCLOSE_WALK_WINDOW", DEFAULT_WALK_WINDOW))

    if not settings.database_url:
        log.error(
            "dayclose_no_persistence_target",
            hint="Set DATABASE_URL; Postgres is the canonical store.",
        )
        return 1

    try:
        top_cid = asyncio.run(discover_wnba_contest_id())
    except Exception as exc:
        log.exception("dayclose_discover_failed", error=str(exc))
        return 1
    if top_cid is None:
        log.warning("dayclose_no_contest_id")
        return 0

    start_id = top_cid - 1
    stop_id = max(1, top_cid - walk_window)
    log.info(
        "dayclose_walk",
        top_cid=top_cid,
        start_id=start_id,
        stop_id=stop_id,
    )
    rc = run_historical_backfill(
        start_id=start_id,
        stop_id=stop_id,
        pause_seconds=0.5,
        dry_run=False,
        with_leaderboards=True,
    )

    # D85: audit yesterday's label coverage against the pool universe so a
    # player silently absent from slate_labels (the 2026-06-08 Loyd/Boston
    # gap) pages instead of permanently losing training labels. Best-effort;
    # never changes the dayclose exit code.
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    try:
        from wnba_oracle.scheduler.watchdog import _check_label_coverage, persist_events

        coverage_events = _check_label_coverage(yesterday)
        if coverage_events:
            persist_events(coverage_events)
        else:
            log.info("dayclose_label_coverage_clean", slate_date=yesterday)
    except Exception as exc:
        log.exception("dayclose_label_coverage_failed", error=str(exc))

    # D90 / D91: auto-record placement against the captured top-20 leaderboard.
    # Best-effort; never changes the dayclose exit code.
    if settings.database_url:
        try:
            _auto_record_placement(yesterday)
        except Exception as exc:
            log.exception("dayclose_auto_placement_failed", error=str(exc))

    # D102: keep wnba_game_logs (the head-training corpus AND the live Tier-0
    # head-feature source) fresh every night, so the rolling windows never go
    # stale and a debuting player still gets head_features the next day. This
    # was the deeper root cause of the D99 C. Leite staleness -- previously the
    # only writer was the manual backfill_minutes.py. Current season only (the
    # one that changes); offseason is a clean no-op. Best-effort, gated by
    # WNBA_DAYCLOSE_REFRESH_GAMELOGS (default on); never changes the exit code.
    if os.environ.get("WNBA_DAYCLOSE_REFRESH_GAMELOGS", "1").strip() not in {"0", "false", ""}:
        try:
            from wnba_oracle.ingest.minutes_backfill import refresh_game_logs

            season = str(dt.date.today().year)
            n = refresh_game_logs([season])
            log.info("dayclose_game_logs_refreshed", season=season, rows=n)
        except Exception as exc:
            log.exception("dayclose_game_logs_refresh_failed", error=str(exc))

    # D102 item 32a: append-only table retention policy. Best-effort cleanup;
    # never changes the dayclose exit code. Truncates old watchdog_events and
    # deletes stale frozen_lineup attempts (keeping only the current freeze_seq).
    try:
        _cleanup_append_only_tables(retention_days=14)
    except Exception as exc:
        log.exception("dayclose_retention_cleanup_failed", error=str(exc))

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
