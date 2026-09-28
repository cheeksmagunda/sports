"""Apply the production HV/TDV train target to offline replay inputs (#620).

``nfl-pipeline train`` filters Corpus G through ``apply_hv_tdv_labels`` and
weights with ``load_contest_boosts``. Replay CLIs use the same helpers so a
walk-forward fit sees the same (player, game) window when Corpus C / HV
exports are linked. When no board is on disk, rows and boosts stay unchanged
(raw-value top-5 weights).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nfl_oracle.recommendations.display_rank_weights import load_contest_boosts
from nfl_oracle.recommendations.hv_labels import apply_hv_tdv_labels
from nfl_oracle.recommendations.model import HistoricalPerformance


@dataclass(frozen=True)
class HvReplayTrainInputs:
    """History rows after the optional HV/TDV filter, plus fit sample boosts."""

    rows: tuple[HistoricalPerformance, ...]
    contest_boosts: dict[tuple[int, int], float] | None
    hv_overlay: dict[str, Any] | None
    applied: bool


def prepare_hv_replay_train_inputs(
    project: Path,
    rows: Sequence[HistoricalPerformance],
    *,
    corpus_c_root: Path | None = None,
    export_root: Path | None = None,
    hv_corpus_root: Path | None = None,
    apply_labels: bool = True,
) -> HvReplayTrainInputs:
    """Filter and weight like production train when HV boards are present.

    ``apply_labels=False`` keeps the caller's rows and only loads boosts.
    When labels are applied and every row is excluded (no linked board), the
    original rows are restored so an offline archive without Corpus C still
    runs under raw-value top-5 weights.
    """

    working: Sequence[HistoricalPerformance] = rows
    overlay: dict[str, Any] | None = None
    applied = False
    if apply_labels:
        kept, audit = apply_hv_tdv_labels(
            project,
            rows,
            corpus_c_root=corpus_c_root,
            export_root=export_root,
            hv_corpus_root=hv_corpus_root,
        )
        overlay = audit.to_dict()
        if kept:
            working = kept
            applied = True
        else:
            overlay = {**overlay, "replay_fallback": "raw_box_no_linked_hv_board"}
    boosts = load_contest_boosts(project, working)
    return HvReplayTrainInputs(
        rows=tuple(working),
        contest_boosts=boosts,
        hv_overlay=overlay,
        applied=applied,
    )


def boost_audit(boosts: Mapping[tuple[int, int], float] | None) -> dict[str, Any]:
    return {
        "contest_display_boost_keys": 0 if not boosts else len(boosts),
        "contest_display_rank": (
            "value_times_top_slot_plus_boost" if boosts else "raw_value_no_boost_map"
        ),
    }
