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


def build_learn_prompt(summary: BoardSummary) -> str:
    return (
        "You are a sports analytics self-learning helper for Highest-value "
        "(HV) and Total Value (TDV) daily fantasy boards.\n"
        "Given the board summary below, write concise structured notes:\n"
        "1) top_1 / max_value signal players\n"
        "2) stacking or correlation guesses (teams)\n"
        "3) one calibration question for the next slate\n"
        "Keep under 250 words. No secrets, no credentials, no URLs with tokens.\n\n"
        f"{summary.prompt_block()}\n"
    )


def write_learning_tick(
    data_root: Path,
    summary: BoardSummary,
    *,
    notes: str,
    model: str,
    gate_reason: str,
    dry_run: bool = False,
) -> Path:
    sport = summary.sport or "unknown"
    slate_id = summary.slate_key or "unknown"
    out_dir = artifact_dir(data_root, sport=sport, slate_id=slate_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_now_iso().replace(":", "").replace("-", "")
    out_path = out_dir / f"tick_{stamp}.json"
    payload: dict[str, Any] = {
        "written_at": utc_now_iso(),
        "gate_reason": gate_reason,
        "model": model,
        "dry_run": dry_run,
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
    prompt = build_learn_prompt(summary)
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
    )
