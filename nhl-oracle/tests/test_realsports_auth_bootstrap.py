from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path

import pytest

from nhl_oracle.ingest import realsports


def _b64gz(payload: dict) -> str:
    raw = json.dumps(payload).encode()
    return base64.b64encode(gzip.compress(raw)).decode()


def _state() -> dict:
    return {"origins": [{"origin": "https://realsports.io", "localStorage": []}]}


def test_materialize_storage_state_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NHL_ORACLE_SCRAPER_DIR", str(tmp_path / "scraper"))
    monkeypatch.setenv("REALSPORTS_STORAGE_STATE_B64GZ", _b64gz(_state()))
    monkeypatch.delenv("NHL_REALSPORTS_STORAGE_STATE", raising=False)
    path = realsports.materialize_storage_state_from_env()
    assert path is not None
    assert path.is_file()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded.get("origins"), list)


def test_materialize_rejects_invalid_b64(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NHL_ORACLE_SCRAPER_DIR", str(tmp_path / "scraper"))
    monkeypatch.setenv("REALSPORTS_STORAGE_STATE_B64GZ", "not-valid-b64")
    monkeypatch.delenv("NHL_REALSPORTS_STORAGE_STATE", raising=False)
    with pytest.raises(realsports.StorageStateMissing):
        realsports.materialize_storage_state_from_env()
