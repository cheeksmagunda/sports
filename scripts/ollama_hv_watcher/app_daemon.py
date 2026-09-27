"""App-driven T-40 helper daemon (#574).

Each sport app fires its own T-40 freeze and serves its frozen five. This
loop only READS the app: for every armed slate it polls the app, copies the
frozen five into a pregame ``hv_board.json`` once the app has frozen, and
writes one advisory ``tick_*.json`` whose ``five_player_lineup`` is exactly
the app's five. Ollama annotates; it never replaces, blocks, or delays the
app's freeze or serving. When Ollama is down a tick is still written with
``notes='ollama_unavailable'``.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from ollama_hv_watcher.adapters import app_api
from ollama_hv_watcher.boards import LIVE_BOARD_FILENAME, load_pregame_board_summary
from ollama_hv_watcher.client import DEFAULT_MODEL
from ollama_hv_watcher.gate import load_manifest_or_empty
from ollama_hv_watcher.learn import run_learn
from ollama_hv_watcher.live import LiveDataRequiredError
from ollama_hv_watcher.serve import DEFAULT_HOST
from ollama_hv_watcher.windows import SlateWindow, load_windows_payload

NowFn = Callable[[], datetime]
SleepFn = Callable[[float], None]
EmitFn = Callable[[dict[str, Any]], None]
WindowFn = Callable[..., SlateWindow]
BoardFn = Callable[..., dict[str, Any] | None]

# Give up polling a day this long after its UTC midnight even if no window
# ever resolved (for example the app never published timing).
DAY_GIVE_UP_AFTER = timedelta(hours=36)


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _emit_json(event: dict[str, Any]) -> None:
    print(json.dumps(event, sort_keys=True), flush=True)


@dataclass
class AppDaemonConfig:
    day: str
    sports: tuple[str, ...]
    data_root: Path = Path("data/ollama_hv")
    windows_json: Path | None = None
    coverage_manifest: Path | None = None
    host: str = DEFAULT_HOST
    model: str = DEFAULT_MODEL
    execute: bool = False
    poll_seconds: float = 30.0
    environ: Mapping[str, str] | None = None


@dataclass
class AppDaemonState:
    ticked: dict[str, str] = field(default_factory=dict)
    ticks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    iterations: int = 0


def _log_error(cfg: AppDaemonConfig, state: AppDaemonState, message: str) -> None:
    state.errors.append(message)
    cfg.data_root.mkdir(parents=True, exist_ok=True)
    with (cfg.data_root / "watcher_errors.log").open("a", encoding="utf-8") as fh:
        fh.write(f"{_iso(datetime.now(UTC))} {message}\n")


def _resolve_windows(
    cfg: AppDaemonConfig,
    state: AppDaemonState,
    *,
    window_fn: WindowFn,
) -> list[SlateWindow]:
    if cfg.windows_json is not None:
        payload = json.loads(Path(cfg.windows_json).read_text(encoding="utf-8"))
        plan = load_windows_payload(payload)
        return [s for s in plan.slates if s.sport in cfg.sports or not cfg.sports]
    out: list[SlateWindow] = []
    for sport in cfg.sports:
        try:
            out.append(window_fn(sport, cfg.day, environ=cfg.environ))
        except (LiveDataRequiredError, app_api.AppApiUnavailableError) as exc:
            _log_error(cfg, state, f"window sport={sport} day={cfg.day} error={exc}")
    return out


def _tick_slate(
    cfg: AppDaemonConfig,
    state: AppDaemonState,
    slate: SlateWindow,
    *,
    board_fn: BoardFn,
    emit: EmitFn,
) -> None:
    session = slate.session_id
    try:
        date.fromisoformat(slate.slate_id)
    except ValueError:
        _log_error(cfg, state, f"skip session={session} slate_id_not_a_day")
        return
    try:
        board = board_fn(
            slate.sport, slate.slate_id, environ=cfg.environ, data_root=cfg.data_root
        )
    except (LiveDataRequiredError, app_api.AppApiUnavailableError) as exc:
        _log_error(cfg, state, f"board session={session} error={exc}")
        return
    if board is None:
        emit({"event": "waiting_for_app_freeze", "session": session})
        return
    frozen_at = str(board.get("frozen_at") or "")
    if state.ticked.get(session) == frozen_at:
        return
    board_path = cfg.data_root / slate.sport / slate.slate_id / LIVE_BOARD_FILENAME
    try:
        summary = load_pregame_board_summary(board_path)
        tick = run_learn(
            summary,
            data_root=cfg.data_root,
            manifest=load_manifest_or_empty(cfg.coverage_manifest),
            host=cfg.host,
            model=cfg.model,
            dry_run=not cfg.execute,
            environ=dict(cfg.environ) if cfg.environ is not None else None,
            record_on_failure=True,
            extra={
                "app_frozen_at": frozen_at,
                "app_source": board.get("source"),
                "session_id": session,
            },
        )
    except (LiveDataRequiredError, ValueError, OSError) as exc:
        _log_error(cfg, state, f"tick session={session} error={exc}")
        return
    state.ticked[session] = frozen_at
    state.ticks.append(str(tick))
    emit(
        {
            "event": "tick_written",
            "session": session,
            "tick": str(tick),
            "app_frozen_at": frozen_at,
            "five": [p.get("name") for p in board.get("players", [])],
        }
    )


def run_app_daemon(
    cfg: AppDaemonConfig,
    *,
    now_fn: NowFn = lambda: datetime.now(UTC),
    sleep_fn: SleepFn = time.sleep,
    window_fn: WindowFn = app_api.slate_window,
    board_fn: BoardFn = app_api.frozen_board,
    emit: EmitFn = _emit_json,
    max_iterations: int | None = None,
) -> dict[str, Any]:
    """Poll armed slates until the latest close; returns a run summary."""

    cfg.data_root.mkdir(parents=True, exist_ok=True)
    state = AppDaemonState()
    give_up_at = (
        datetime.combine(date.fromisoformat(cfg.day), datetime.min.time(), UTC)
        + DAY_GIVE_UP_AFTER
    )
    windows: list[SlateWindow] = []
    while True:
        state.iterations += 1
        now = now_fn()
        windows = _resolve_windows(cfg, state, window_fn=window_fn)
        armed = [w for w in windows if w.is_armed(now)]
        pending = [w for w in windows if w.is_before_arm(now)]
        emit(
            {
                "event": "poll",
                "now": _iso(now),
                "armed": [w.session_id for w in armed],
                "pending": {w.session_id: _iso(w.arm_at) for w in pending},
            }
        )
        for slate in armed:
            _tick_slate(cfg, state, slate, board_fn=board_fn, emit=emit)
        if windows and not armed and not pending:
            break  # every slate closed
        if not windows and now >= give_up_at:
            break
        if max_iterations is not None and state.iterations >= max_iterations:
            break
        sleep_s = cfg.poll_seconds
        if pending and not armed:
            until_arm = min(w.arm_at for w in pending) - now
            sleep_s = min(sleep_s, max(1.0, until_arm.total_seconds()))
        sleep_fn(max(1.0, sleep_s))
    return {
        "iterations": state.iterations,
        "ticks": state.ticks,
        "ticked_sessions": dict(state.ticked),
        "errors": state.errors,
        "windows": [w.to_dict() for w in windows],
    }
