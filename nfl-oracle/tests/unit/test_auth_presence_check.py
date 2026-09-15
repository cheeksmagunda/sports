"""auth_presence_check must see volume-backed Real Sports session files."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _import():
    sys.path.insert(0, str(SCRIPTS))
    try:
        module = importlib.import_module("auth_presence_check")
        return importlib.reload(module)
    finally:
        sys.path.remove(str(SCRIPTS))


def test_reports_volume_backed_storage_and_token_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    volume = tmp_path / "volume"
    scraper = volume / "scraper"
    scraper.mkdir(parents=True)
    (scraper / "storage_state.json").write_text("{}")
    (scraper / "request_token_cache.json").write_text("{}")
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(volume))
    monkeypatch.delenv("NFL_ORACLE_SCRAPER_DIR", raising=False)
    monkeypatch.delenv("REALSPORTS_STORAGE_STATE_PATH", raising=False)
    monkeypatch.delenv("NFL_REALSPORTS_STORAGE_STATE", raising=False)
    monkeypatch.delenv("REALSPORTS_STORAGE_STATE_B64GZ", raising=False)

    mod = _import()
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "scraper_storage_state=yes" in out
    assert "token_cache_exists=yes" in out
    assert "live_ingest_ready=yes" in out
    assert str(scraper / "storage_state.json") in out
