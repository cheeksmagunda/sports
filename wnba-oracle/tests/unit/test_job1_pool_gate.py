"""D84: degraded job1 pool is a hard error, not a quiet log line.

pool_sanity returns failure reasons; run() persists first (forensics),
then writes a critical watchdog event and main() exits nonzero so the
Railway cron run shows failed. The 2026-06-08 morning capture
(1 row, 1 team) trips both checks.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from wnba_oracle.scheduler import job1
from wnba_oracle.scheduler.job1 import Job1Result, pool_sanity


def _rows(n: int, teams: list[str]) -> list[dict]:
    return [{"team": teams[i % len(teams)]} for i in range(n)]


def test_incident_shape_one_row_one_team_fails_both() -> None:
    reasons = pool_sanity(_rows(1, ["LVA"]), min_pool=12, min_teams=2)
    assert len(reasons) == 2
    assert any("n_pool=1" in r for r in reasons)
    assert any("n_teams=1" in r for r in reasons)


def test_empty_pool_fails() -> None:
    reasons = pool_sanity([], min_pool=12, min_teams=2)
    assert len(reasons) == 2


def test_healthy_slate_passes() -> None:
    teams = [f"T{i}" for i in range(12)]
    assert pool_sanity(_rows(60, teams), min_pool=12, min_teams=2) == []


def test_row_floor_scales_with_team_count() -> None:
    # 6 teams demand 18 rows even though min_pool is 12.
    teams = [f"T{i}" for i in range(6)]
    reasons = pool_sanity(_rows(14, teams), min_pool=12, min_teams=2)
    assert len(reasons) == 1
    assert "floor 18" in reasons[0]


def test_two_team_minimum_edge_passes() -> None:
    assert pool_sanity(_rows(12, ["AAA", "BBB"]), min_pool=12, min_teams=2) == []


def test_blank_teams_do_not_count() -> None:
    rows = [{"team": ""} for _ in range(20)]
    reasons = pool_sanity(rows, min_pool=12, min_teams=2)
    assert any("n_teams=0" in r for r in reasons)


def test_main_exits_nonzero_on_degraded_pool() -> None:
    degraded = Job1Result("2026-06-08", 1, 0, 0, 1, ("n_pool=1 below floor 12",))
    with patch.object(job1, "run", return_value=degraded):
        assert job1.main() == 1


def test_main_exits_zero_on_healthy_pool() -> None:
    healthy = Job1Result("2026-06-08", 60, 3, 30, 60)
    with patch.object(job1, "run", return_value=healthy):
        assert job1.main() == 0


def test_valid_capture_replaces_the_whole_slate_atomically() -> None:
    conn = MagicMock()
    rows = [
        {"slate_date": "2026-06-08", "player_id": 1},
        {"slate_date": "2026-06-08", "player_id": 2},
    ]

    persisted = job1._replace_enrichment(conn, "2026-06-08", rows)

    assert persisted == 2
    assert conn.execute.call_count == 3
    first = conn.execute.call_args_list[0]
    assert str(first.args[0]) == str(job1.JOB1_DELETE_SLATE)
    assert first.args[1] == {"slate_date": "2026-06-08"}
    assert [call.args[1] for call in conn.execute.call_args_list[1:]] == rows


def test_enrichment_row_preserves_provider_signal_shape() -> None:
    player = SimpleNamespace(
        platform_id="123",
        display_name="A. Wilson",
        first_name="A'ja",
        last_name="Wilson",
        team="LVA",
        injury_status="",
        primary_ranking=1,
        position="F",
        multiplier_bonus=1.5,
        game_start_utc="2026-06-08T23:00:00Z",
    )
    context = job1._EnrichmentContext(
        team_to_opp={"LVA": "NYL"},
        team_to_vegas={"LVA": {"vegas_total": 164.5, "vegas_spread": -4.0, "is_home": 1.0}},
        rotowire=job1._index_rotowire([]),
        minutes={},
        head_features={},
        resolver=None,
        team_stats={},
        opponent_dvp={"NYL": 2.1},
        props={
            ("a. wilson", "player_points"): {
                "line": 22.5,
                "implied_over_prob": 0.52,
                "implied_under_prob": 0.48,
            }
        },
    )

    rows, stats, misses = job1._build_enrichment_rows("2026-06-08", [player], context)

    assert len(rows) == 1
    assert rows[0]["player_id"] == 123
    assert rows[0]["opponent"] == "NYL"
    features = json.loads(rows[0]["features_json"])
    assert features["vegas_total"] == 164.5
    assert features["prop_points_line"] == 22.5
    assert features["game_start_utc"] == "2026-06-08T23:00:00Z"
    assert stats.props_matched == 1
    assert misses == ["A. Wilson (LVA) [unresolved]"]
