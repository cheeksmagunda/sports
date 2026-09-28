"""Write self-learning notes/ticks from HV board summaries via Ollama (#574).

For a sport app's frozen board the tick's ``five_player_lineup`` is exactly
the app's five in the app's slot order; Ollama only annotates. When Ollama
is down or times out a tick is still written (``notes='ollama_unavailable'``)
so the app's five are always recorded.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from realsports_corpus.coverage_manifest import CoverageManifest, OllamaForbiddenError

from ollama_hv_watcher.boards import BoardSummary
from ollama_hv_watcher.client import DEFAULT_HOST, DEFAULT_MODEL, generate
from ollama_hv_watcher.gate import ensure_ollama_training_allowed
from ollama_hv_watcher.pick import (
    APP_FROZEN_SECTION,
    CHALK_VS_MULTIPLIER_PRINCIPLE,
    FIVE_PLAYER_LINEUP_SIZE,
    lineup_for_summary,
    lineup_prompt_block,
)
from ollama_hv_watcher.sim import sim_report

OLLAMA_UNAVAILABLE_NOTES = "ollama_unavailable"
OLLAMA_GATE_FORBIDDEN_NOTES = "ollama_gate_forbidden"
LATEST_TICK_FILENAME = "latest_tick.json"


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


def atomic_write_json(path: Path, payload: Any) -> Path:
    """Write JSON via a same-directory temp file and ``os.replace``."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return path


def build_learn_prompt(
    summary: BoardSummary,
    *,
    lineup: tuple[dict[str, Any], ...] | None = None,
) -> str:
    card = lineup if lineup is not None else lineup_for_summary(summary)
    header = (
        "You are a decisive sports analytics controller for Highest-value "
        "(HV) and Total Value (TDV) daily fantasy contests.\n"
        f"HARD RULE: every slate day locks exactly "
        f"{FIVE_PLAYER_LINEUP_SIZE} distinct players in slot order "
        f"1..{FIVE_PLAYER_LINEUP_SIZE}. Never propose fewer. Never propose "
        "more. Never reorder after freeze.\n"
        f"CORE PRINCIPLE: {CHALK_VS_MULTIPLIER_PRINCIPLE}\n"
    )
    if summary.section == APP_FROZEN_SECTION:
        tasks = (
            "The five-player card below is the sport app's FROZEN lineup. "
            "It is final: do not replace, reorder, or add players. All data "
            "is PRE-GAME projection only.\n"
            "Write concise structured annotations:\n"
            "1) why each slot can outpace the crowd on the Highest value / "
            "Total Value leaderboard\n"
            "2) top_1 / max_value signal and the biggest single risk\n"
            "3) stacking or correlation notes (teams / games) inside the five\n"
            "4) one calibration question to check after the slate settles\n"
        )
    else:
        tasks = (
            "The five-player card is the total-draft-value simulation "
            "(value * (slot + boost)), already chosen. Do not replace it. "
            "Write concise notes on that sim:\n"
            "1) why slot 1 leads committed total value\n"
            "2) the single biggest risk to that total\n"
            "3) stacking or correlation inside the five\n"
            "4) one calibration question after the slate settles\n"
        )
    return (
        header
        + tasks
        + "Keep under 250 words. No secrets, no credentials, no URLs with "
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
    extra: dict[str, Any] | None = None,
) -> Path:
    sport = summary.sport or "unknown"
    slate_id = summary.slate_key or "unknown"
    out_dir = artifact_dir(data_root, sport=sport, slate_id=slate_id)
    stamp = (
        datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        + f"{datetime.now(UTC).microsecond:06d}Z"
    )
    out_path = out_dir / f"tick_{stamp}.json"
    card = lineup if lineup is not None else lineup_for_summary(summary)
    selection = (
        "app_frozen_lineup"
        if summary.section == APP_FROZEN_SECTION
        else "total_draft_value_sim"
    )
    payload: dict[str, Any] = {
        "written_at": utc_now_iso(),
        "gate_reason": gate_reason,
        "model": model,
        "dry_run": dry_run,
        "phase": summary.phase,
        "lineup_source": selection,
        "lineup_size": FIVE_PLAYER_LINEUP_SIZE,
        "five_player_lineup": list(card),
        "sim": sim_report(card, sport=summary.sport or "", selection=selection),
        "board": summary.to_dict(),
        "notes": notes,
    }
    if extra:
        payload.update(extra)
    atomic_write_json(out_path, payload)
    # Stable pointer for env-gated picker tilt / tooling (#574).
    latest_payload = {
        **payload,
        "tick_path": out_path.name,
    }
    atomic_write_json(out_dir / LATEST_TICK_FILENAME, latest_payload)
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
    record_on_failure: bool = False,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Run one advisory tick.

    ``record_on_failure=True`` (daemon path) never raises for an Ollama
    outage or a closed gate: it writes a tick with the lineup and
    ``notes='ollama_unavailable'`` / ``'ollama_gate_forbidden'`` instead.
    """

    card = lineup_for_summary(summary)
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
            extra=extra,
        )
    try:
        reason = ensure_ollama_training_allowed(manifest, environ=environ)
    except OllamaForbiddenError as exc:
        if not record_on_failure:
            raise
        return write_learning_tick(
            data_root,
            summary,
            notes=OLLAMA_GATE_FORBIDDEN_NOTES,
            model=model,
            gate_reason="forbidden",
            dry_run=False,
            lineup=card,
            extra={**(extra or {}), "ollama_error": str(exc)[:500]},
        )
    try:
        notes = generate(prompt, host=host, model=model)
    except (RuntimeError, OSError, TimeoutError) as exc:
        if not record_on_failure:
            raise
        return write_learning_tick(
            data_root,
            summary,
            notes=OLLAMA_UNAVAILABLE_NOTES,
            model=model,
            gate_reason=reason,
            dry_run=False,
            lineup=card,
            extra={**(extra or {}), "ollama_error": str(exc)[:500]},
        )
    return write_learning_tick(
        data_root,
        summary,
        notes=notes,
        model=model,
        gate_reason=reason,
        dry_run=False,
        lineup=card,
        extra=extra,
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
    record_on_failure: bool = False,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write ``advice.json`` for the same pregame board a learn tick uses.

    Default callers pass ``dry_run=True``. ``record_on_failure=True`` writes
    rank-fallback tilts when Ollama is down so a learn tick is never dropped
    because advice failed. Apps ignore the file unless their influence env
    is on.
    """

    from ollama_hv_watcher.advice import (
        build_advice_prompt,
        tilts_from_ollama_notes,
        write_advice,
    )

    prompt = build_advice_prompt(summary)
    if dry_run:
        return write_advice(
            data_root,
            summary,
            tilts=tilts_from_ollama_notes("", summary),
            model=model,
            gate_reason="dry_run",
            dry_run=True,
            extra={**(extra or {}), "prompt_prepared": True},
        )
    try:
        reason = ensure_ollama_training_allowed(manifest, environ=environ)
    except OllamaForbiddenError as exc:
        if not record_on_failure:
            raise
        return write_advice(
            data_root,
            summary,
            tilts=tilts_from_ollama_notes("", summary),
            model=model,
            gate_reason="forbidden",
            dry_run=False,
            extra={**(extra or {}), "ollama_error": str(exc)[:500]},
        )
    try:
        notes = generate(prompt, host=host, model=model)
    except (RuntimeError, OSError, TimeoutError) as exc:
        if not record_on_failure:
            raise
        return write_advice(
            data_root,
            summary,
            tilts=tilts_from_ollama_notes("", summary),
            model=model,
            gate_reason=reason,
            dry_run=False,
            extra={
                **(extra or {}),
                "ollama_error": str(exc)[:500],
                "fallback": "rank_tilt",
            },
        )
    return write_advice(
        data_root,
        summary,
        tilts=tilts_from_ollama_notes(notes, summary),
        model=model,
        gate_reason=reason,
        dry_run=False,
        extra=extra,
    )
