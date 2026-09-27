"""RS field matrix + corpus key dump scaffold (#523 / #526)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from nfl_oracle.features.rs_field_map import mapped_rs_field_count, rs_field_matrix


def test_rs_field_matrix_has_required_columns() -> None:
    rows = rs_field_matrix()
    assert rows
    for row in rows:
        assert set(row) == {
            "rs_field",
            "ingest_path",
            "durable_store",
            "own_model_slot",
            "status",
        }
        assert row["status"] in {
            "mapped",
            "gap",
            "leakage-blocked",
            "unused",
            "label",
        }
    assert mapped_rs_field_count() >= 6
    assert any(r["status"] == "label" for r in rows)
    assert any(r["status"] == "leakage-blocked" for r in rows)


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
