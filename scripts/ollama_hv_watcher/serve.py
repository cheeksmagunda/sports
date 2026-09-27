"""systemd-less Ollama serve helpers: health curl, pidfile, nohup (#574)."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_PIDFILE = Path("data/ollama_hv/ollama_serve.pid")
DEFAULT_WATCHER_PIDFILE = Path("data/ollama_hv/watcher.pid")
DEFAULT_LOG = Path("data/ollama_hv/ollama_serve.log")


def health_check(host: str = DEFAULT_HOST, *, timeout_s: float = 2.0) -> dict[str, Any]:
    url = f"{host.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc), "host": host}
    models = []
    if isinstance(payload, dict) and isinstance(payload.get("models"), list):
        models = [
            m.get("name")
            for m in payload["models"]
            if isinstance(m, dict) and m.get("name")
        ]
    return {"ok": True, "host": host, "models": models}


def read_pidfile(path: Path) -> int | None:
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        return int(raw.splitlines()[0].strip())
    except ValueError:
        return None


def pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def write_pidfile(path: Path, pid: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{pid}\n", encoding="utf-8")


def remove_pidfile(path: Path) -> None:
    path = Path(path)
    if path.is_file():
        path.unlink()


def ensure_ollama_serve(
    *,
    host: str = DEFAULT_HOST,
    pidfile: Path = DEFAULT_PIDFILE,
    logfile: Path = DEFAULT_LOG,
    wait_s: float = 20.0,
) -> dict[str, Any]:
    """Start ``ollama serve`` via nohup when healthcheck fails."""

    status = health_check(host)
    if status.get("ok"):
        return {"started": False, "health": status, "pid": read_pidfile(pidfile)}

    logfile = Path(logfile)
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with logfile.open("ab") as log_fh:
        # start_new_session detaches like nohup; avoid wrapping with a shell.
        proc = subprocess.Popen(  # noqa: S603
            ["ollama", "serve"],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    write_pidfile(pidfile, proc.pid)

    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        status = health_check(host)
        if status.get("ok"):
            return {"started": True, "health": status, "pid": proc.pid}
        time.sleep(0.5)

    return {
        "started": True,
        "health": status,
        "pid": proc.pid,
        "error": "healthcheck_timeout",
    }


def stop_pidfile_process(pidfile: Path, *, sig: int = signal.SIGTERM) -> dict[str, Any]:
    pid = read_pidfile(pidfile)
    if pid is None:
        return {"stopped": False, "reason": "no_pidfile"}
    if not pid_is_alive(pid):
        remove_pidfile(pidfile)
        return {"stopped": False, "reason": "not_running", "pid": pid}
    os.kill(pid, sig)
    remove_pidfile(pidfile)
    return {"stopped": True, "pid": pid}
