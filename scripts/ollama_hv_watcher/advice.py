"""Slate-shape advice for optional app influence (#574).

The Codespace helper writes ``advice.json`` during the T-40 to close
window. Apps tilt projected scores only when their default-OFF
``*_OLLAMA_INFLUENCE`` env is enabled. Stale, missing, or malformed advice
is ignored. This module never talks to Railway or the apps.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from oracle_core.slate_advice import (
    DEFAULT_MAX_AGE_SECONDS,
    MULT_MAX,
    MULT_MIN,
    clamp_mult,
)

from ollama_hv_watcher.boards import BoardSummary
from ollama_hv_watcher.pick import (
    CHALK_VS_MULTIPLIER_PRINCIPLE,
    FIVE_PLAYER_LINEUP_SIZE,
    OBSERVED_SLOT_MULTIPLIERS,
)

ADVICE_FILENAME = "advice.json"
RANK_TILT_STEP = 0.03


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def advice_path(data_root: Path, *, sport: str, slate_id: str) -> Path:
    return (
        Path(data_root)
        / sport.replace("/", "_")
        / slate_id.replace("/", "_")
        / ADVICE_FILENAME
    )


def build_advice_prompt(summary: BoardSummary) -> str:
    multis = ", ".join(
        f"slot{i}={m}x" for i, m in enumerate(OBSERVED_SLOT_MULTIPLIERS, start=1)
    )
    return (
        "You are a slate-shape advisor for a five-player Highest-value / "
        "Total Value contest (NFL max_value / WNBA TDV serve shape). "
        "Return ONLY one JSON object (no markdown) with:\n"
        '  "tilts": [ {"player_id": <id>, "name": <str>, "mult": <float>}, ... ]\n'
        f"Rules: at most {FIVE_PLAYER_LINEUP_SIZE} tilts; mult in "
        f"[{MULT_MIN}, {MULT_MAX}]; 1.0 is neutral.\n"
        f"PRINCIPLE: {CHALK_VS_MULTIPLIER_PRINCIPLE}\n"
        f"Slot multipliers: {multis}. Lift true HV/TDV; fade soft chalk. "
        "Never invent player_ids not on the board. Pregame only: do not use "
        "played-game outcomes.\n\n"
        f"{summary.prompt_block(top_n=20)}\n"
    )


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = text.strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def tilts_from_ollama_notes(
    notes: str,
    summary: BoardSummary,
) -> list[dict[str, Any]]:
    """Parse Ollama JSON tilts; fall back to a mild rank tilt on the top five."""

    board_ids = {
        str(row.get("player_id"))
        for row in summary.top_players
        if row.get("player_id") is not None
    }
    by_id = {
        str(row.get("player_id")): row
        for row in summary.top_players
        if row.get("player_id") is not None
    }
    payload = _extract_json_object(notes)
    tilts: list[dict[str, Any]] = []
    if payload is not None:
        rows = payload.get("tilts")
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                pid = row.get("player_id")
                if pid is None or str(pid) not in board_ids:
                    continue
                try:
                    mult = clamp_mult(float(row.get("mult", 1.0)))
                except (TypeError, ValueError):
                    continue
                if abs(mult - 1.0) < 1e-9:
                    continue
                src = by_id[str(pid)]
                tilts.append(
                    {
                        "player_id": pid,
                        "name": row.get("name") or src.get("name"),
                        "mult": mult,
                    }
                )
                if len(tilts) >= FIVE_PLAYER_LINEUP_SIZE:
                    break
    if tilts:
        return tilts
    for index, row in enumerate(summary.top_players[:FIVE_PLAYER_LINEUP_SIZE]):
        pid = row.get("player_id")
        if pid is None:
            continue
        mult = clamp_mult(
            1.0
            + RANK_TILT_STEP
            * (FIVE_PLAYER_LINEUP_SIZE - index)
            / FIVE_PLAYER_LINEUP_SIZE
        )
        tilts.append({"player_id": pid, "name": row.get("name"), "mult": mult})
    return tilts


def write_advice(
    data_root: Path,
    summary: BoardSummary,
    *,
    tilts: list[dict[str, Any]],
    model: str,
    gate_reason: str,
    dry_run: bool = False,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    extra: dict[str, Any] | None = None,
) -> Path:
    out = advice_path(data_root, sport=summary.sport, slate_id=summary.slate_key)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema": "ollama_slate_advice_v1",
        "written_at": utc_now_iso(),
        "sport": summary.sport,
        "slate_id": summary.slate_key,
        "model": model,
        "gate_reason": gate_reason,
        "dry_run": dry_run,
        "max_age_seconds": int(max_age_seconds),
        "tilts": tilts,
        "principle": CHALK_VS_MULTIPLIER_PRINCIPLE,
        "board": summary.to_dict(),
    }
    if extra:
        payload["extra"] = extra
    tmp = out.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(out)
    return out


def advice_written_at(path: Path) -> datetime | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw = payload.get("written_at")
        if not raw:
            return None
        return datetime.fromisoformat(str(raw)).astimezone(UTC)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
