from __future__ import annotations

import base64
import gzip
import json

import pytest

from nfl_oracle.ingest import realsports


def _state() -> dict[str, object]:
    return {"cookies": [], "origins": []}


def _b64gz(payload: dict[str, object]) -> str:
    return base64.b64encode(gzip.compress(json.dumps(payload).encode())).decode()


def test_storage_state_materializes_from_b64gz(tmp_path, monkeypatch):
    monkeypatch.setenv("NFL_ORACLE_SCRAPER_DIR", str(tmp_path))
    monkeypatch.setenv("REALSPORTS_STORAGE_STATE_B64GZ", _b64gz(_state()))
    monkeypatch.delenv("NFL_REALSPORTS_STORAGE_STATE", raising=False)

    path = realsports.materialize_storage_state_from_env()

    assert path == tmp_path / "storage_state.json"
    assert path is not None
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text()) == _state()


def test_placeholder_b64gz_does_not_mask_raw_storage_state(tmp_path, monkeypatch):
    monkeypatch.setenv("NFL_ORACLE_SCRAPER_DIR", str(tmp_path))
    monkeypatch.setenv("REALSPORTS_STORAGE_STATE_B64GZ", "placeholder")
    monkeypatch.setenv("NFL_REALSPORTS_STORAGE_STATE", json.dumps(_state()))

    path = realsports.materialize_storage_state_from_env()

    assert path == tmp_path / "storage_state.json"
    assert path is not None
    assert json.loads(path.read_text()) == _state()


def test_placeholder_storage_state_path_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("NFL_ORACLE_SCRAPER_DIR", str(tmp_path))
    monkeypatch.setenv("NFL_REALSPORTS_STORAGE_STATE", "placeholder")
    # storage_state_path falls back to a sibling wnba-oracle/scraper session
    # before giving up. That file exists on an operator's machine and not in
    # CI, so without pinning the project root this passes remotely and fails
    # locally -- which teaches everyone to ignore a red suite.
    monkeypatch.setattr(realsports, "project_root", lambda: tmp_path)

    assert realsports.storage_state_path() == tmp_path / "storage_state.json"


def test_invalid_b64gz_still_fails_closed(monkeypatch):
    monkeypatch.setenv("REALSPORTS_STORAGE_STATE_B64GZ", "not-valid-b64")
    monkeypatch.delenv("NFL_REALSPORTS_STORAGE_STATE", raising=False)

    with pytest.raises(realsports.StorageStateMissing, match="REALSPORTS_STORAGE_STATE_B64GZ"):
        realsports.materialize_storage_state_from_env()


def test_scraper_dir_uses_railway_volume_mount(tmp_path, monkeypatch):
    volume = tmp_path / "volume"
    volume.mkdir()
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(volume))
    monkeypatch.delenv("NFL_ORACLE_SCRAPER_DIR", raising=False)

    path = realsports.scraper_dir()

    assert path == volume / "scraper"
    assert path.is_dir()
    assert path.stat().st_mode & 0o777 == 0o700


def test_scraper_dir_explicit_override_beats_volume(tmp_path, monkeypatch):
    volume = tmp_path / "volume"
    volume.mkdir()
    override = tmp_path / "explicit"
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(volume))
    monkeypatch.setenv("NFL_ORACLE_SCRAPER_DIR", str(override))

    path = realsports.scraper_dir()

    assert path == override
    assert not (volume / "scraper").exists()


def test_storage_state_discovers_volume_copy_before_creating_default(tmp_path, monkeypatch):
    volume = tmp_path / "volume"
    scraper = volume / "scraper"
    scraper.mkdir(parents=True)
    existing = scraper / "storage_state.json"
    existing.write_text('{"cookies":[],"origins":[]}')
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(volume))
    monkeypatch.delenv("NFL_ORACLE_SCRAPER_DIR", raising=False)
    monkeypatch.delenv("REALSPORTS_STORAGE_STATE_PATH", raising=False)
    monkeypatch.delenv("NFL_REALSPORTS_STORAGE_STATE", raising=False)
    monkeypatch.setattr(realsports, "project_root", lambda: tmp_path / "missing-project")

    assert realsports.storage_state_path() == existing


def test_storage_state_discovers_legacy_ephemeral_when_volume_empty(tmp_path, monkeypatch):
    volume = tmp_path / "volume"
    volume.mkdir()
    legacy_dir = tmp_path / "project" / "scraper"
    legacy_dir.mkdir(parents=True)
    legacy = legacy_dir / "storage_state.json"
    legacy.write_text('{"cookies":[],"origins":[]}')
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(volume))
    monkeypatch.delenv("NFL_ORACLE_SCRAPER_DIR", raising=False)
    monkeypatch.delenv("REALSPORTS_STORAGE_STATE_PATH", raising=False)
    monkeypatch.delenv("NFL_REALSPORTS_STORAGE_STATE", raising=False)
    monkeypatch.setattr(realsports, "project_root", lambda: tmp_path / "project")

    assert realsports.storage_state_path() == legacy


def test_materialize_writes_under_volume_scraper(tmp_path, monkeypatch):
    volume = tmp_path / "volume"
    volume.mkdir()
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(volume))
    monkeypatch.delenv("NFL_ORACLE_SCRAPER_DIR", raising=False)
    monkeypatch.setenv("REALSPORTS_STORAGE_STATE_B64GZ", _b64gz(_state()))
    monkeypatch.delenv("NFL_REALSPORTS_STORAGE_STATE", raising=False)

    path = realsports.materialize_storage_state_from_env()

    assert path == volume / "scraper" / "storage_state.json"
    assert path is not None
    assert path.stat().st_mode & 0o777 == 0o600

