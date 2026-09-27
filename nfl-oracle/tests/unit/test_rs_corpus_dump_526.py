"""Corpus key-dump scaffold (#526)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def test_dump_exposed_keys_walks_fixture() -> None:
    root = Path(__file__).resolve().parents[3]
    script = root / "scripts/rs_corpus/dump_exposed_keys.py"
    spec = importlib.util.spec_from_file_location("rs_dump_exposed_keys", script)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fixture = root / "drive/nfl_fixtures/contest_2124_stats.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    keys = set(mod.walk_keys(payload))
    assert "contest.id" in keys
    assert "draftStats[]" in keys
