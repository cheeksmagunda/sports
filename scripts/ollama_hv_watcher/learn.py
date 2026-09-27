"""Write self-learning notes/ticks from HV board summaries via Ollama (#574)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from realsports_corpus.coverage_manifest import CoverageManifest

from ollama_hv_watcher.advice import (
    build_advice_prompt,
    tilts_from_ollama_notes,
    write_advice,
)
from ollama_hv_watcher.boards import BoardSummary
from ollama_hv_watcher.client import DEFAULT_HOST, DEFAULT_MODEL, generate
from ollama_hv_watcher.gate import ensure_ollama_training_allowed
from ollama_hv_watcher.pick import (
    CHALK_VS_MULTIPLIER_PRINCIPLE,
    FIVE_PLAYER_LINEUP_SIZE,
    OBSERVED_SLOT_MULTIPLIERS,
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
        f"CORE PRINCIPLE: {CHALK_VS_MULTIPLIER_PRINCIPLE}\n"
        "Serve shape: NFL max_value + WNBA total_draft_value (TDV). Reject "
        "cash/diversified drift.\n"
        "Given the board + proposed five-player card below, write concise "
        "structured notes:\n"
        "1) confirm or replace the five-player card (still exactly five)\n"
        "2) top_1 / max_value signal and why slot 1 earns the 2.0x multiplier\n"
        "3) chalk-vs-multiplier: which picks are true HV chalk (keep high "
        "slots) vs soft chalk (fade) vs low-draft leverage (slot them high "
        "only when value is real)\n"
        "4) stacking or correlation guesses (teams) inside the five\n"
        "5) one calibration question for the next slate\n"
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
        "slot_multipliers": list(OBSERVED_SLOT_MULTIPLIERS),
        "principle": CHALK_VS_MULTIPLIER_PRINCIPLE,
        "serve_shape": {
            "nfl": "max_value",
            "wnba": "total_draft_value",
        },
        "five_player_lineup": list(card),
        "board": summary.to_dict(),
        "notes": notes,
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    out_path.write_text(text, encoding="utf-8")
    # Stable pointer for tooling / optional app tilt mounts.
    latest = out_dir / "latest_tick.json"
    latest.write_text(text, encoding="utf-8")
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


def run_advice(
    summary: BoardSummary,
    *,
    data_root: Path,
    manifest: CoverageManifest,
    host: str = DEFAULT_HOST,
    model: str = DEFAULT_MODEL,
    dry_run: bool = False,
    environ: dict[str, str] | None = None,
) -> Path:
    """Write pre-freeze ``advice.json`` tilts for optional app influence."""

    prompt = build_advice_prompt(summary)
    if dry_run:
        # Rank fallback tilts so dry-run still produces a usable advice file.
        tilts = tilts_from_ollama_notes("", summary)
        return write_advice(
            data_root,
            summary,
            tilts=tilts,
            model=model,
            gate_reason="dry_run",
            dry_run=True,
            extra={"prompt_prepared": True},
        )
    reason = ensure_ollama_training_allowed(manifest, environ=environ)
    notes = generate(prompt, host=host, model=model)
    tilts = tilts_from_ollama_notes(notes, summary)
    return write_advice(
        data_root,
        summary,
        tilts=tilts,
        model=model,
        gate_reason=reason,
        dry_run=False,
        extra={"notes_excerpt": notes[:500]},
    )
