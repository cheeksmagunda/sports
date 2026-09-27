"""Portfolio Real Sports contest corpus layout and export stubs (#526).

Durable history lives in a separate GitHub-tracked corpus repo. This package
owns the monorepo layout contract, coverage_manifest schema, and offline-safe
export stubs from existing WNBA / NFL durable stores.
"""

from __future__ import annotations

from realsports_corpus.coverage_manifest import (
    CoverageManifest,
    OllamaForbiddenError,
    assert_ollama_helper_forbidden,
    build_empty_manifest,
    is_historical_capture_complete,
    ollama_helper_allowed,
)
from realsports_corpus.layout import (
    REQUIRED_VARIABLE_FAMILIES,
    SPORTS,
    SlateKey,
    VariableFamily,
    ensure_kind_roots,
    ensure_slate_layout,
    family_dir,
    kind_root,
)

__all__ = [
    "REQUIRED_VARIABLE_FAMILIES",
    "SPORTS",
    "CoverageManifest",
    "OllamaForbiddenError",
    "SlateKey",
    "VariableFamily",
    "assert_ollama_helper_forbidden",
    "build_empty_manifest",
    "ensure_kind_roots",
    "ensure_slate_layout",
    "family_dir",
    "is_historical_capture_complete",
    "kind_root",
    "ollama_helper_allowed",
]
