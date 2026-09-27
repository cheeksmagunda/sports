"""Slate-shape advice for optional app influence (#574).

Codespace helper writes ``advice.json`` BEFORE each app's T-40 freeze.
Apps may tilt projected scores from that file when their default-OFF
``*_OLLAMA_INFLUENCE`` env is enabled. Stale / missing / malformed advice
is ignored (identity). This module never talks to Railway or the apps.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ollama_hv_watcher.boards import BoardSummary
from ollama_hv_watcher.pick import (
    CHALK_VS_MULTIPLIER_PRINCIPLE,
    FIVE_PLAYER_LINEUP_SIZE,
    OBSERVED_SLOT_MULTIPLIERS,
)

ADVICE_FILENAME = "advice.json"
DEFAULT_MAX_AGE_SECONDS = 3 * 60 * 60  # 3h: enough for prepare→freeze
MULT_MIN = 0.85
MULT_MAX = 1.15
# Soft default tilt magnitude when Ollama only ranks without explicit mults.
RANK_TILT_STEP = 0.03


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_utc(value: str) -> datetime:
    text = str(value).strip().replace("Z", "+00:00")
    return datetime.fromisoformat(text).astimezone(UTC)


def clamp_mult(value: float) -> float:
    return max(MULT_MIN, min(MULT_MAX, float(value)))


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
        f"Slot multipliers: {multis}. Lift true HV/TDV (especially names "
        "that deserve slot-1 2.0x); fade soft chalk (high drafts, weak "
        "value). Never invent player_ids not on the board.\n\n"
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
    """Parse Ollama JSON tilts; fall back to top-five mild rank tilts."""

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
    # Fallback: mild lift on the ranked five so advice is never empty noise.
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


def load_advice_payload(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def advice_is_fresh(
    payload: dict[str, Any],
    *,
    sport: str,
    slate_id: str,
    now: datetime | None = None,
) -> bool:
    if str(payload.get("sport") or "").lower() != sport.lower():
        return False
    if str(payload.get("slate_id") or "") != str(slate_id):
        return False
    written_raw = payload.get("written_at")
    if not written_raw:
        return False
    try:
        written = parse_iso_utc(str(written_raw))
    except ValueError:
        return False
    try:
        max_age = int(payload.get("max_age_seconds") or DEFAULT_MAX_AGE_SECONDS)
    except (TypeError, ValueError):
        max_age = DEFAULT_MAX_AGE_SECONDS
    clock = now if now is not None else datetime.now(UTC)
    age = (clock - written).total_seconds()
    return 0.0 <= age <= float(max_age)


def tilt_map_from_payload(payload: dict[str, Any]) -> dict[int, float]:
    rows = payload.get("tilts")
    if not isinstance(rows, list):
        return {}
    out: dict[int, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = row.get("player_id")
        if pid is None:
            continue
        try:
            player_id = int(pid)
            mult = clamp_mult(float(row.get("mult", 1.0)))
        except (TypeError, ValueError):
            continue
        if abs(mult - 1.0) < 1e-9:
            continue
        out[player_id] = mult
    return out
