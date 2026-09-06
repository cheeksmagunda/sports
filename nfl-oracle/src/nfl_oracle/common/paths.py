"""Project-owned runtime path discovery for nfl-oracle."""

from __future__ import annotations

from pathlib import Path


def resolve_project_root(module_file: str | Path) -> Path:
    """Return the NFL application root for source and non-editable installs."""
    source_root = Path(module_file).resolve().parents[3]
    working_root = Path.cwd().resolve()
    candidates = (source_root, working_root, working_root / "nfl-oracle")
    for candidate in candidates:
        if (candidate / "src" / "nfl_oracle").is_dir():
            return candidate
    return source_root
