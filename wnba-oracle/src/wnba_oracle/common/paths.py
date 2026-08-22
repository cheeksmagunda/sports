"""Project-owned runtime path discovery.

Non-editable workspace installs place package modules under ``site-packages``
while models, data, and scraper state remain in the application checkout.
Resolve the checkout without relying on an editable install or a fixed host
path. Container imports still resolve directly from ``/app/wnba-oracle/src``.
"""

from __future__ import annotations

from pathlib import Path


def resolve_project_root(module_file: str | Path) -> Path:
    """Return the WNBA application root for source and non-editable installs."""
    source_root = Path(module_file).resolve().parents[3]
    working_root = Path.cwd().resolve()
    candidates = (source_root, working_root, working_root / "wnba-oracle")
    for candidate in candidates:
        if (candidate / "src" / "wnba_oracle").is_dir():
            return candidate
    return source_root
