"""HV training alignment keeps a center at her F-fallback level (#623).

The shipped alpha was shrunk against F. Writing a lower C mean without
moving that alpha drops an A'ja-class center. The paired update shifts
the alpha by the same gap, so her served level stays put. A blank pool
position does not relabel her as F, and the focus slate's score stays
out of the gap.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backtest_eb_cohort_impact.py"
HV = "highestBoostedValuePlayers"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("backtest_eb_cohort_impact", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _row(pid: int, name: str, position: str, score: float) -> dict:
    return {
        "input": {
            "real_sports_player_id": pid,
            "display_name": name,
            "position": position,
            "card_boost": 0.0,
            "team": "LVA",
        },
        "label": {
            "platform_player_id": pid,
            "display_name": name,
            "section": HV,
            "real_score": score,
            "card_boost": 0.0,
        },
    }


def _dossier(entries: list[dict]) -> dict:
    return {
        "input_snapshot": {"rows": [entry["input"] for entry in entries]},
        "realized_player_results": {"rows": [entry["label"] for entry in entries]},
    }


def test_paired_shift_keeps_center_at_fallback_when_cohort_mean_is_lower() -> None:
    mod = _load_script()
    low_centers = [
        _row(691, "S. Austin", "C", 2.0),
        _row(627, "A. Boston", "C-F", 2.0),
    ]
    forwards = [
        _row(650, "N. Collier", "F", 6.0),
        _row(755, "A. Kuier", "F", 6.0),
        _row(617, "N. Hillmon", "F", 6.0),
    ]

    def slate(wilson_position: str, wilson_score: float) -> dict:
        return _dossier(
            [_row(598, "A. Wilson", wilson_position, wilson_score), *low_centers, *forwards]
        )

    dossiers = {
        "2026-09-17": slate("C", 9.0),
        "2026-09-20": slate("", 9.0),
        "2026-09-24": slate("C", 9.0),
        "2026-09-27": slate("C", 0.0),
    }
    stored = {598: 2.0, 650: 0.4}
    artifact_f = 2.5
    overrides, means = mod._aligned_alpha_overrides(
        dossiers,
        score_slates={"2026-09-17", "2026-09-20", "2026-09-24"},
        position_slates=set(dossiers),
        stored_alpha=stored,
        artifact_f_mean=artifact_f,
    )
    assert means["C"] < means["F"]
    served = means["C"] + overrides[598]
    fallback = artifact_f + stored[598]
    assert abs(served - fallback) < 1e-9
    # Mean-only swap: the failure that dropped Wilson on 2026-09-27.
    assert means["C"] + stored[598] < served - 0.05
    assert mod._modal_positions(dossiers, slates=set(dossiers))[598] == "C"


def test_focus_slate_score_does_not_enter_the_cohort_gap() -> None:
    mod = _load_script()
    dossiers = {
        "2026-09-24": _dossier(
            [_row(598, "A. Wilson", "C", 4.0), _row(650, "N. Collier", "F", 4.0)]
        ),
        "2026-09-27": _dossier(
            [_row(598, "A. Wilson", "C", 19.0), _row(650, "N. Collier", "F", 1.0)]
        ),
    }
    _overrides, means = mod._aligned_alpha_overrides(
        dossiers,
        score_slates={"2026-09-24"},
        position_slates=set(dossiers),
        stored_alpha={598: 1.0, 650: 1.0},
        artifact_f_mean=2.5,
    )
    assert abs(means["C"] - 2.5) < 1e-9
    assert abs(means["F"] - 2.5) < 1e-9
