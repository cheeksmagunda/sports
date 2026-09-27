"""NBA-owned data path helpers (local / volume roots)."""

from __future__ import annotations

import os
from pathlib import Path


def app_root() -> Path:
    """Return the NBA application root for source and non-editable installs."""

    return Path(__file__).resolve().parents[3]


def data_root() -> Path:
    """Prefer Railway volume mount, else app-local ``data/``."""

    volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if volume:
        return Path(volume).expanduser()
    return app_root() / "data"


def corpus_g_root() -> Path:
    return data_root() / "corpus_g"


def coverage_matrix_path() -> Path:
    return data_root() / "coverage" / "season_matrix.json"
