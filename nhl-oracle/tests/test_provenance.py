from __future__ import annotations

import json
from pathlib import Path

from nhl_oracle.ingest.provenance import NhlCorpusStore


def test_persist_endpoint_writes_payload_and_provenance(tmp_path: Path) -> None:
    store = NhlCorpusStore(tmp_path)
    artifact = store.persist_endpoint(
        game_id=1,
        season=2026,
        endpoint="boxscore",
        payload={"players": []},
        source_url="https://example.invalid/boxscore",
        captured_at="2026-10-01T00:00:00Z",
    )
    assert artifact.wrote is True
    assert artifact.path.is_file()
    assert artifact.provenance_path.is_file()
    saved = json.loads(artifact.provenance_path.read_text(encoding="utf-8"))
    assert saved["content_sha256"] == artifact.provenance.content_sha256
    assert saved["game_id"] == 1
    assert saved["redacted"] is True


def test_persist_endpoint_is_idempotent_on_unchanged_content(tmp_path: Path) -> None:
    store = NhlCorpusStore(tmp_path)
    first = store.persist_endpoint(
        game_id=2,
        season=2026,
        endpoint="roster",
        payload={"a": 1},
        source_url="https://example.invalid/roster",
        captured_at="2026-10-01T00:00:00Z",
    )
    second = store.persist_endpoint(
        game_id=2,
        season=2026,
        endpoint="roster",
        payload={"a": 1},
        source_url="https://example.invalid/roster",
        captured_at="2026-10-01T00:05:00Z",
    )
    assert first.wrote is True
    assert second.wrote is False
    assert first.provenance.content_sha256 == second.provenance.content_sha256


def test_persist_endpoint_rewrites_on_changed_content(tmp_path: Path) -> None:
    store = NhlCorpusStore(tmp_path)
    first = store.persist_endpoint(
        game_id=3,
        season=2026,
        endpoint="contest",
        payload={"a": 1},
        source_url="https://example.invalid/contest",
        captured_at="2026-10-01T00:00:00Z",
    )
    second = store.persist_endpoint(
        game_id=3,
        season=2026,
        endpoint="contest",
        payload={"a": 2},
        source_url="https://example.invalid/contest",
        captured_at="2026-10-01T00:05:00Z",
    )
    assert first.wrote is True
    assert second.wrote is True
    assert first.provenance.content_sha256 != second.provenance.content_sha256
