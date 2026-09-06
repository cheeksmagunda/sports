#!/usr/bin/env python3
"""Minimal daily-shadow scaffold (observation only; no contest entry).

Pipeline hooks (STATUS Codespace checklist / #91 shadow):
  1) Corpus G coverage matrix refresh (offline --refresh-matrix-only)
  2) Label extract + walk-forward baselines (nfl-value-baselines)
  3) Status artifact under data/artifacts/ (gitignored)

Does not authenticate to Real Sports, does not call Railway, does not enter contests.
Intended to run in Codespace (or any workspace with deps installed).
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "data" / "artifacts"
CT = ZoneInfo("America/Chicago")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def _uv(*args: str) -> list[str]:
    return ["uv", "run", "--frozen", "--package", "nfl-oracle", *args]


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(CT)
    stamp = started.strftime("%Y%m%dT%H%M%S%z")
    artifact_path = ARTIFACT_DIR / f"daily_shadow_{stamp}.json"

    steps: dict[str, object] = {
        "role": "daily-shadow",
        "issue_shadow": "#91",
        "contest_entry": False,
        "started_at_ct": started.isoformat(),
        "clock_fields_contract": [
            "event_time",
            "source_available_at",
            "captured_at",
            "decision_at",
        ],
    }

    # 1) coverage → matrix refresh (offline; no network)
    cov = _run(_uv("nfl-corpus-g-backfill", "--refresh-matrix-only"))
    steps["coverage"] = {
        "cmd": "nfl-corpus-g-backfill --refresh-matrix-only",
        "returncode": cov.returncode,
        "stdout_tail": (cov.stdout or "")[-2000:],
        "stderr_tail": (cov.stderr or "")[-1000:],
    }

    # 2) labels/baselines
    base = _run(_uv("nfl-value-baselines", "--json"))
    baseline_payload: object
    if base.returncode == 0 and (base.stdout or "").strip():
        try:
            baseline_payload = json.loads(base.stdout)
        except json.JSONDecodeError:
            baseline_payload = {"raw_stdout_tail": (base.stdout or "")[-2000:]}
    else:
        baseline_payload = {
            "error": True,
            "returncode": base.returncode,
            "stdout_tail": (base.stdout or "")[-2000:],
            "stderr_tail": (base.stderr or "")[-1000:],
        }
    steps["baselines"] = baseline_payload

    finished = datetime.now(CT)
    steps["finished_at_ct"] = finished.isoformat()
    steps["ok"] = cov.returncode == 0 and base.returncode == 0

    artifact_path.write_text(json.dumps(steps, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest = ARTIFACT_DIR / "daily_shadow_latest.json"
    latest.write_text(artifact_path.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"daily_shadow: wrote {artifact_path}")
    print(f"daily_shadow: wrote {latest}")
    print(
        "daily_shadow: "
        f"ok={steps['ok']} coverage_rc={cov.returncode} baselines_rc={base.returncode}"
    )
    return 0 if steps["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
