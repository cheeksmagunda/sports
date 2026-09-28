"""Portfolio HV/TDV slate watcher loop (issue #574).

Arms at earliest T-40 across discovered slates, stays alive until latest
slate close, and optionally runs offline learn ticks when the Ollama gate
allows (coverage_manifest complete or ``SPORTS_OLLAMA_UNLOCK=1``).
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ollama_hv_watcher.boards import armed_board_paths, load_pregame_board_summary
from ollama_hv_watcher.discover import discover_day_plan
from ollama_hv_watcher.gate import (
    ensure_ollama_training_allowed,
    load_manifest_or_empty,
)
from ollama_hv_watcher.learn import run_advice, run_learn
from ollama_hv_watcher.live import LiveDataRequiredError
from ollama_hv_watcher.pick import FIVE_PLAYER_LINEUP_SIZE
from ollama_hv_watcher.serve import (
    DEFAULT_HOST,
    DEFAULT_WATCHER_PIDFILE,
    ensure_ollama_serve,
    health_check,
    pid_is_alive,
    read_pidfile,
    remove_pidfile,
    write_pidfile,
)
from ollama_hv_watcher.windows import DayWatchPlan, load_windows_payload

SleepFn = Callable[[float], None]
NowFn = Callable[[], datetime]


@dataclass(frozen=True)
class WatcherConfig:
    """Runtime knobs for one Codespace watcher process."""

    data_root: Path = Path("data/ollama_hv")
    windows_json: Path | None = None
    coverage_manifest: Path | None = None
    host: str = DEFAULT_HOST
    model: str = "llama3.2:3b"
    poll_seconds: float = 30.0
    learn: bool = True
    dry_run: bool = False
    ensure_serve: bool = True
    include_fixtures: bool = False
    pidfile: Path = DEFAULT_WATCHER_PIDFILE


def utc_now() -> datetime:
    return datetime.now(UTC)


def resolve_plan(cfg: WatcherConfig) -> DayWatchPlan:
    """Load LIVE slate windows or raise ``LiveDataRequiredError`` loudly."""

    return discover_day_plan(
        windows_json=cfg.windows_json,
        include_fixtures=cfg.include_fixtures,
    )


def status_snapshot(
    cfg: WatcherConfig, *, now: datetime | None = None
) -> dict[str, Any]:
    now = now or utc_now()
    health = health_check(cfg.host)
    plan: DayWatchPlan | None
    plan_error: str | None = None
    try:
        plan = resolve_plan(cfg)
    except LiveDataRequiredError as exc:
        plan = None
        plan_error = str(exc)
    manifest = load_manifest_or_empty(cfg.coverage_manifest)
    gate: dict[str, Any]
    try:
        reason = ensure_ollama_training_allowed(manifest)
        gate = {"allowed": True, "reason": reason}
    except Exception as exc:  # noqa: BLE001 - surface gate text in status
        gate = {"allowed": False, "error": str(exc)}
    payload: dict[str, Any] = {
        "now": now.isoformat().replace("+00:00", "Z"),
        "ollama": health,
        "gate": gate,
        "live_only": not cfg.include_fixtures,
        "five_player_lineup_size": FIVE_PLAYER_LINEUP_SIZE,
        "data_root": str(cfg.data_root),
        "pidfile": str(cfg.pidfile),
        "watcher_pid": read_pidfile(cfg.pidfile),
        "watcher_alive": bool(
            (pid := read_pidfile(cfg.pidfile)) is not None and pid_is_alive(pid)
        ),
        "plan": None if plan is None else plan.to_dict(),
        "plan_error": plan_error,
    }
    if plan is not None:
        payload["should_run"] = plan.should_run(now)
        payload["active_sessions"] = [s.session_id for s in plan.active_sessions(now)]
    return payload


def _learn_once(
    cfg: WatcherConfig, plan: DayWatchPlan, *, now: datetime | None = None
) -> list[str]:
    """Learn on armed slates' PREGAME boards only (never data_root/boards)."""

    written: list[str] = []
    manifest = load_manifest_or_empty(cfg.coverage_manifest)
    paths = armed_board_paths(cfg.data_root, plan.active_sessions(now or utc_now()))
    for path in paths:
        try:
            summary = load_pregame_board_summary(path)
            out = run_learn(
                summary,
                data_root=cfg.data_root,
                manifest=manifest,
                host=cfg.host,
                model=cfg.model,
                dry_run=cfg.dry_run,
            )
            written.append(str(out))
            try:
                advice = run_advice(
                    summary,
                    data_root=cfg.data_root,
                    manifest=manifest,
                    host=cfg.host,
                    model=cfg.model,
                    dry_run=cfg.dry_run,
                    record_on_failure=True,
                )
                written.append(str(advice))
            except (OSError, RuntimeError, ValueError) as exc:
                err_path = cfg.data_root / "watcher_errors.log"
                with err_path.open("a", encoding="utf-8") as fh:
                    fh.write(f"board={path} advice_error={exc}\n")
        except ValueError as exc:
            # Fail closed on short boards (<5 players) without killing the day.
            err_path = cfg.data_root / "watcher_errors.log"
            with err_path.open("a", encoding="utf-8") as fh:
                fh.write(f"board={path} error={exc}\n")
    return written


def run_watch_loop(
    cfg: WatcherConfig,
    *,
    now_fn: NowFn = utc_now,
    sleep_fn: SleepFn = time.sleep,
    max_iterations: int | None = None,
) -> dict[str, Any]:
    """Poll until past latest slate close (or max_iterations for tests).

    Requires LIVE windows JSON (or explicit fixtures). Missing calendars raise
    ``LiveDataRequiredError`` immediately - no placeholder wait loop.
    """

    cfg.data_root.mkdir(parents=True, exist_ok=True)
    write_pidfile(cfg.pidfile, os.getpid())

    if cfg.ensure_serve:
        ensure_ollama_serve(host=cfg.host)

    iterations = 0
    learned: list[str] = []
    last_plan: DayWatchPlan | None = None
    try:
        while True:
            iterations += 1
            now = now_fn()
            plan = resolve_plan(cfg)
            last_plan = plan
            if now < plan.arm_at:
                sleep_fn(
                    min(cfg.poll_seconds, max(0.0, (plan.arm_at - now).total_seconds()))
                )
            elif plan.should_run(now):
                if cfg.learn:
                    try:
                        learned.extend(_learn_once(cfg, plan, now=now))
                    except Exception as exc:  # noqa: BLE001 - keep watcher alive
                        err_path = cfg.data_root / "watcher_errors.log"
                        with err_path.open("a", encoding="utf-8") as fh:
                            fh.write(f"{now.isoformat()} learn_error={exc}\n")
                sleep_fn(cfg.poll_seconds)
            else:
                break
            if max_iterations is not None and iterations >= max_iterations:
                break
    finally:
        remove_pidfile(cfg.pidfile)

    return {
        "iterations": iterations,
        "learned": learned,
        "plan": None if last_plan is None else last_plan.to_dict(),
    }


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def plan_from_payload(payload: dict[str, Any] | list[Any]) -> DayWatchPlan:
    return load_windows_payload(payload)
