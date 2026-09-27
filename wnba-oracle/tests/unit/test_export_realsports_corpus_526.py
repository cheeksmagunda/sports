"""Unit tests for WNBA Real Sports corpus export layout (#526)."""

from __future__ import annotations

import json
from pathlib import Path

from wnba_oracle.corpus.realsports_export import (
    HV_SECTION,
    export_slates,
    fake_demo_rows,
    label_row_to_player,
    slate_dir,
    write_slate_shard,
)


def test_fake_demo_rows_cover_hv_and_other_sections() -> None:
    labels, boards = fake_demo_rows()
    sections = {row["section"] for row in labels}
    assert HV_SECTION in sections
    assert "popularPlayers" in sections
    assert len(boards) == 2
    assert boards[0]["rank"] == 1


def test_write_slate_shard_layout(tmp_path: Path) -> None:
    labels, boards = fake_demo_rows()
    summary = write_slate_shard(
        tmp_path,
        slate_date="2026-09-25",
        label_rows=labels,
        leaderboard_rows=boards,
        exported_at="2026-09-27T00:00:00Z",
    )
    assert summary.hv_rows == 2
    assert summary.draft_stats_rows == 3
    assert summary.lineup_rows == 2
    assert summary.path == "sport=wnba/season=2026/slate=2026-09-25"

    shard = slate_dir(tmp_path, "2026-09-25")
    tv = json.loads((shard / "total_value_leaderboard.json").read_text(encoding="utf-8"))
    assert tv["section"] == HV_SECTION
    assert tv["player_count"] == 2
    # Higher real_score / value first among HV rows.
    assert tv["players"][0]["player_id"] == 11
    assert tv["players"][0]["value"] == 42.5
    assert set(tv["players"][0]) >= {
        "player_id",
        "name",
        "team",
        "real_score",
        "base",
        "card_boost",
        "slot",
        "drafts",
        "value",
    }

    jsonl_lines = (
        (shard / "draft_stats_all_sections.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    assert len(jsonl_lines) == 3
    parsed = [json.loads(line) for line in jsonl_lines]
    assert {row["section"] for row in parsed} == {HV_SECTION, "popularPlayers"}

    lineups = json.loads((shard / "lineups_top20.json").read_text(encoding="utf-8"))
    assert lineups["recorded_state_count"] == 2
    assert lineups["recorded_states"][0]["rank"] == 1
    assert isinstance(lineups["recorded_states"][0]["lineup"], list)

    manifest = json.loads((shard / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["files"]) == {
        "total_value_leaderboard.json",
        "draft_stats_all_sections.jsonl",
        "lineups_top20.json",
    }
    assert manifest["files"]["total_value_leaderboard.json"]["rows"] == 2
    assert len(manifest["files"]["draft_stats_all_sections.jsonl"]["sha256"]) == 64


def test_export_slates_updates_coverage_index(tmp_path: Path) -> None:
    labels, boards = fake_demo_rows()
    # Second slate with labels only.
    labels = [
        *labels,
        {
            "contest_id": 2200,
            "slate_date": "2026-09-26",
            "section": HV_SECTION,
            "platform_player_id": 44,
            "display_name": "D. Player",
            "team_key": "NYL",
            "card_boost": 1.0,
            "drafts": 10,
            "real_score": 20.0,
            "ingested_at": "2026-09-27T06:00:00Z",
        },
    ]
    summaries = export_slates(tmp_path, label_rows=labels, leaderboard_rows=boards)
    assert len(summaries) == 2
    coverage = json.loads(
        (tmp_path / "manifest" / "coverage_wnba.json").read_text(encoding="utf-8")
    )
    assert coverage["slate_count"] == 2
    assert coverage["slates"]["2026-09-25"]["hv_rows"] == 2
    assert coverage["slates"]["2026-09-26"]["lineup_rows"] == 0


def test_export_slates_filter(tmp_path: Path) -> None:
    labels, boards = fake_demo_rows()
    summaries = export_slates(
        tmp_path,
        label_rows=labels,
        leaderboard_rows=boards,
        slate_dates=["2026-09-25"],
    )
    assert len(summaries) == 1
    assert summaries[0].slate_date == "2026-09-25"


def test_label_row_to_player_maps_provider_value() -> None:
    player = label_row_to_player(
        {
            "contest_id": 1,
            "slate_date": "2026-01-01",
            "section": HV_SECTION,
            "platform_player_id": 7,
            "display_name": "X",
            "team_key": "SEA",
            "card_boost": 0.25,
            "drafts": None,
            "real_score": 12.5,
            "ingested_at": None,
        }
    )
    assert player["player_id"] == 7
    assert player["base"] == 12.5
    assert player["value"] == 12.5
    assert player["slot"] is None
    assert player["drafts"] is None
