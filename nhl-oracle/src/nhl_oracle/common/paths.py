"""Project-owned runtime path discovery for nhl-oracle."""

from __future__ import annotations

from pathlib import Path


def resolve_project_root(module_file: str | Path) -> Path:
    """Return the NHL application root for source and non-editable installs."""

    source_root = Path(module_file).resolve().parents[3]
    working_root = Path.cwd().resolve()
    candidates = (source_root, working_root, working_root / "nhl-oracle")
    for candidate in candidates:
        if (candidate / "src" / "nhl_oracle").is_dir():
            return candidate
    return source_root
