"""Write self-learning notes/ticks from HV board summaries via Ollama (#574)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from realsports_corpus.coverage_manifest import CoverageManifest

from ollama_hv_watcher.boards import BoardSummary
from ollama_hv_watcher.client import DEFAULT_HOST, DEFAULT_MODEL, generate
from ollama_hv_watcher.gate import ensure_ollama_training_allowed
from ollama_hv_watcher.pick import (
    FIVE_PLAYER_LINEUP_SIZE,
    five_player_lineup,
    lineup_prompt_block,
)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def artifact_dir(
    data_root: Path,
    *,
    sport: str,
    slate_id: str,
) -> Path:
    safe_sport = sport.replace("/", "_")
    safe_slate = slate_id.replace("/", "_")
    return Path(data_root) / safe_sport / safe_slate


def build_learn_prompt(
    summary: BoardSummary,
    *,
    lineup: tuple[dict[str, Any], ...] | None = None,
) -> str:
    card = lineup if lineup is not None else five_player_lineup(summary)
    return (
        "You are a decisive sports analytics controller for Highest-value "
        "(HV) and Total Value (TDV) daily fantasy contests.\n"
        f"HARD RULE: every slate day locks exactly "
        f"{FIVE_PLAYER_LINEUP_SIZE} distinct players in slot order "
        f"1..{FIVE_PLAYER_LINEUP_SIZE}. Never propose fewer. Never propose "
        "more. Never reorder after freeze.\n"
        "Given the board + proposed five-player card below, write concise "
        "structured notes:\n"
        "1) confirm or replace the five-player card (still exactly five)\n"
        "2) top_1 / max_value signal and why slot 1 is that player\n"
        "3) stacking or correlation guesses (teams) inside the five\n"
        "4) one calibration question for the next slate\n"
        "Keep under 250 words. No secrets, no credentials, no URLs with "
        "tokens.\n\n"
        f"{summary.prompt_block()}\n\n"
        f"{lineup_prompt_block(card)}\n"
    )


def write_learning_tick(
    data_root: Path,
    summary: BoardSummary,
    *,
    notes: str,
    model: str,
    gate_reason: str,
    dry_run: bool = False,
    lineup: tuple[dict[str, Any], ...] | None = None,
) -> Path:
    sport = summary.sport or "unknown"
    slate_id = summary.slate_key or "unknown"
    out_dir = artifact_dir(data_root, sport=sport, slate_id=slate_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_now_iso().replace(":", "").replace("-", "")
    out_path = out_dir / f"tick_{stamp}.json"
    card = lineup if lineup is not None else five_player_lineup(summary)
    payload: dict[str, Any] = {
        "written_at": utc_now_iso(),
        "gate_reason": gate_reason,
        "model": model,
        "dry_run": dry_run,
        "lineup_size": FIVE_PLAYER_LINEUP_SIZE,
        "five_player_lineup": list(card),
        "board": summary.to_dict(),
        "notes": notes,
    }
    out_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return out_path


def run_learn(
    summary: BoardSummary,
    *,
    data_root: Path,
    manifest: CoverageManifest,
    host: str = DEFAULT_HOST,
    model: str = DEFAULT_MODEL,
    dry_run: bool = False,
    environ: dict[str, str] | None = None,
) -> Path:
    card = five_player_lineup(summary)
    prompt = build_learn_prompt(summary, lineup=card)
    if dry_run:
        notes = (
            "[dry_run] prompt prepared; Ollama generate skipped.\n"
            f"gate=deferred_until_execute\n\n{prompt}"
        )
        return write_learning_tick(
            data_root,
            summary,
            notes=notes,
            model=model,
            gate_reason="dry_run",
            dry_run=True,
            lineup=card,
        )
    reason = ensure_ollama_training_allowed(manifest, environ=environ)
    notes = generate(prompt, host=host, model=model)
    return write_learning_tick(
        data_root,
        summary,
        notes=notes,
        model=model,
        gate_reason=reason,
        dry_run=False,
        lineup=card,
    )
