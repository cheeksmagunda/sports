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

    assert realsports.storage_state_path() == tmp_path / "storage_state.json"


def test_invalid_b64gz_still_fails_closed(monkeypatch):
    monkeypatch.setenv("REALSPORTS_STORAGE_STATE_B64GZ", "not-valid-b64")
    monkeypatch.delenv("NFL_REALSPORTS_STORAGE_STATE", raising=False)

    with pytest.raises(realsports.StorageStateMissing, match="REALSPORTS_STORAGE_STATE_B64GZ"):
        realsports.materialize_storage_state_from_env()
