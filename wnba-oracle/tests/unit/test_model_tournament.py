from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "model_tournament.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("model_tournament", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tournament_harness_writes_comparisons(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    out = tmp_path / "results"
    monkeypatch.setattr(
        "sys.argv",
        [
            "model_tournament.py",
            "--output-dir",
            str(out),
            "--baseline-artifact",
            str(tmp_path / "baseline.pkl"),
            "--challenger-artifacts",
            str(tmp_path / "challenger.pkl"),
        ],
    )

    assert module.main() == 0
    payload = json.loads((out / "tournament_results.json").read_text())
    assert payload["comparisons"]
    assert payload["variants"]
