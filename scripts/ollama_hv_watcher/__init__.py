"""Codespace Ollama HV/TDV self-learning slate watcher (#574).

Arms at earliest T-40 across sports, stays until latest slate close, learns
offline from HV/TDV boards when the coverage_manifest gate (or
``SPORTS_OLLAMA_UNLOCK=1``) allows. Artifacts under ``data/ollama_hv/``.
"""

from __future__ import annotations

from ollama_hv_watcher.boards import (
    BoardSummary,
    load_board_summary,
    summarize_board_payload,
)
from ollama_hv_watcher.discover import discover_day_plan
from ollama_hv_watcher.gate import ensure_ollama_training_allowed
from ollama_hv_watcher.windows import (
    DEFAULT_T40_MINUTES,
    DayWatchPlan,
    SlateWindow,
    build_day_plan,
    build_portfolio_window,
    parse_iso_utc,
)

__all__ = [
    "DEFAULT_T40_MINUTES",
    "BoardSummary",
    "DayWatchPlan",
    "SlateWindow",
    "__version__",
    "build_day_plan",
    "build_portfolio_window",
    "discover_day_plan",
    "ensure_ollama_training_allowed",
    "load_board_summary",
    "parse_iso_utc",
    "summarize_board_payload",
]

__version__ = "0.1.0"
