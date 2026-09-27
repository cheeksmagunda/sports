"""Tests for WNBA draftStats / recorded_states corpus export (#526)."""

from __future__ import annotations

import json
from pathlib import Path

from wnba_oracle.corpus.draft_stats_export import (
    HV_SECTION,
    export_slates,
    fake_demo_rows,
    write_section_catalog,
)


def test_export_dumps_every_section_and_hv_board(tmp_path: Path) -> None:
    labels, leaderboards = fake_demo_rows()
    summaries = export_slates(
        tmp_path,
        label_rows=labels,
        leaderboard_rows=leaderboards,
    )
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.slate_date == "2026-09-24"
    assert summary.hv_rows == 1
    assert summary.recorded_draft_stats_rows == 4
    assert summary.recorded_lineup_rows == 1
    assert set(summary.sections) == {
        HV_SECTION,
        "popularPlayers",
        "mostCommon3xPlayers",
        "leaderboard_lineup",
    }

    tv_path = tmp_path / summary.tv_path
    draft_path = tmp_path / summary.recorded_draft_stats_path
    lineups_path = tmp_path / summary.recorded_lineups_path
    assert tv_path.is_file()
    assert draft_path.is_file()
    assert lineups_path.is_file()

    tv = json.loads(tv_path.read_text(encoding="utf-8"))
    assert tv["section"] == HV_SECTION
    assert tv["train_label"] is True
    assert tv["player_count"] == 1
    assert tv["players"][0]["player_id"] == 11

    lines = [json.loads(line) for line in draft_path.read_text(encoding="utf-8").splitlines()]
    assert {row["section"] for row in lines} == set(summary.sections)
    non_hv = [row for row in lines if row["section"] != HV_SECTION]
    assert non_hv
    assert all(row["train_label"] is False for row in non_hv)
    assert all(row["role"] == "recorded_state" for row in non_hv)

    lineups = json.loads(lineups_path.read_text(encoding="utf-8"))
    assert lineups["train_label"] is False
    assert lineups["role"] == "recorded_state"
    assert lineups["entries"][0]["lineup"][0]["playerId"] == 11

    catalog = json.loads(
        (tmp_path / "manifest" / "draft_stats_sections.json").read_text(encoding="utf-8")
    )
    assert catalog["hv_section"] == HV_SECTION
    assert "popularPlayers" in {s["name"] for s in catalog["sections"]}


def test_write_section_catalog_alone(tmp_path: Path) -> None:
    path = write_section_catalog(tmp_path)
    assert path.name == "draft_stats_sections.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert "mostDrafted" in {s["name"] for s in doc["sections"]}
