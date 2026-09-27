"""Ollama training gate: coverage_manifest complete OR operator unlock (#574)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from realsports_corpus.coverage_manifest import (
    CoverageManifest,
    OllamaForbiddenError,
    assert_ollama_helper_forbidden,
    build_empty_manifest,
    load_coverage_manifest,
    ollama_helper_allowed,
)

UnlockReason = Literal["coverage_complete", "operator_unlock"]

UNLOCK_ENV = "SPORTS_OLLAMA_UNLOCK"


def operator_unlock_enabled(environ: dict[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    return str(env.get(UNLOCK_ENV, "")).strip() == "1"


def load_manifest_or_empty(path: Path | None) -> CoverageManifest:
    if path is None or not Path(path).is_file():
        return build_empty_manifest()
    return load_coverage_manifest(Path(path))


def training_allowed(
    manifest: CoverageManifest,
    *,
    environ: dict[str, str] | None = None,
) -> bool:
    return operator_unlock_enabled(environ) or ollama_helper_allowed(manifest)


def ensure_ollama_training_allowed(
    manifest: CoverageManifest,
    *,
    environ: dict[str, str] | None = None,
) -> UnlockReason:
    """Allow Ollama generate/learn when coverage is complete or unlock is set.

    Binary install + ``ollama serve`` healthchecks are always allowed; this
    gate applies to training / prompt generation only.
    """

    if operator_unlock_enabled(environ):
        return "operator_unlock"
    if ollama_helper_allowed(manifest):
        return "coverage_complete"
    assert_ollama_helper_forbidden(manifest)
    raise OllamaForbiddenError("unreachable")
