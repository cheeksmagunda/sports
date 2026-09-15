"""capture_storage_state must write under volume-aware scraper_dir."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _import():
    sys.path.insert(0, str(SCRIPTS))
    try:
        module = importlib.import_module("capture_storage_state")
        return importlib.reload(module)
    finally:
        sys.path.remove(str(SCRIPTS))


def test_capture_target_uses_railway_volume_scraper(tmp_path, monkeypatch) -> None:
    volume = tmp_path / "vol"
    volume.mkdir()
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(volume))
    monkeypatch.delenv("NFL_ORACLE_SCRAPER_DIR", raising=False)

    mod = _import()
    target = mod.capture_target_path()
    assert target == volume / "scraper" / "storage_state.json"
    assert target.parent == volume / "scraper"


def test_capture_target_honors_explicit_scraper_dir(tmp_path, monkeypatch) -> None:
    custom = tmp_path / "custom-scraper"
    monkeypatch.setenv("NFL_ORACLE_SCRAPER_DIR", str(custom))
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(tmp_path / "ignored-vol"))

    mod = _import()
    target = mod.capture_target_path()
    assert target == custom / "storage_state.json"


def test_profile_dir_lives_under_same_scraper(tmp_path, monkeypatch) -> None:
    volume = tmp_path / "vol"
    volume.mkdir()
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(volume))
    monkeypatch.delenv("NFL_ORACLE_SCRAPER_DIR", raising=False)

    mod = _import()
    profile = mod._profile_dir()
    assert profile == volume / "scraper" / "chrome_profile"
    assert profile.is_dir()
