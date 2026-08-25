"""Pure helper tests for read-only stacking-decision analytics."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "analyze_stacking_decisions.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("analyze_stacking_decisions", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _decision(**overrides):
    decision = {
        "policy_version": "contextual-stacking-v1",
        "reason": "best_projected_balanced",
        "metadata_quality": "provider_game_id",
        "slate_game_count": 2,
        "selected_game_count": 2,
        "selected_team_count": 4,
        "selected_max_players_per_game": 3,
        "selected_max_players_per_team": 2,
        "preferred_min_games": 2,
        "preferred_team_count": 4,
        "preferred_max_players_per_game": 3,
        "objective_sacrifice": 0.0,
    }
    decision.update(overrides)
    return decision


def _row(decision_marker="missing", **overrides):
    lineup = {"player_ids": [1, 2, 3, 4, 5]}
    if decision_marker != "missing":
        lineup["stack_decision"] = decision_marker
    row = {
        "slate_date": "2026-08-25",
        "lineup": lineup,
        "placement_recorded_at": None,
        "placement_source": None,
        "entry_rank": None,
        "entry_count": None,
        "finish_percentile": None,
        "placement_metadata_json": None,
    }
    row.update(overrides)
    return row


def test_summary_separates_versioned_legacy_and_malformed_rows() -> None:
    analytics = _load_script()
    rows = [
        _row(_decision()),
        _row(),
        _row({"reason": "missing_version"}),
        _row("not-an-object"),
    ]

    summary = analytics.summarize_rows(rows)

    assert summary["rows"] == {
        "total": 4,
        "versioned": 1,
        "legacy_uninstrumented": 1,
        "malformed_or_unversioned": 2,
    }
    version = summary["decisions"]["policy_versions"]["contextual-stacking-v1"]
    assert version == {"count": 1, "rate": 1.0}


def test_reason_rates_use_only_versioned_decisions() -> None:
    analytics = _load_script()
    rows = [
        _row(_decision(reason="team_balance_within_margin")),
        _row(_decision(reason="team_balance_within_margin")),
        _row(_decision(reason="contextual_ev_override")),
        _row(),
    ]

    reasons = analytics.summarize_rows(rows)["decisions"]["reasons"]

    assert reasons["team_balance_within_margin"]["count"] == 2
    assert reasons["team_balance_within_margin"]["rate"] == pytest.approx(2 / 3)
    assert reasons["contextual_ev_override"] == {"count": 1, "rate": pytest.approx(1 / 3)}


def test_composition_rate_excludes_unknown_shapes_from_denominator() -> None:
    analytics = _load_script()
    rows = [
        _row(_decision()),
        _row(_decision(selected_game_count=1)),
        _row(
            _decision(
                metadata_quality="incomplete",
                selected_game_count=None,
                selected_max_players_per_game=None,
                preferred_min_games=None,
                preferred_max_players_per_game=None,
            )
        ),
    ]

    composition = analytics.summarize_rows(rows)["decisions"]["composition"]

    assert composition["preferred"] == 1
    assert composition["concentrated"] == 1
    assert composition["unknown"] == 1
    assert composition["determinate_denominator"] == 2
    assert composition["preferred_rate"] == 0.5
    assert composition["concentrated_rate"] == 0.5


def test_placement_coverage_keeps_exact_censored_and_unknown_separate() -> None:
    analytics = _load_script()
    rows = [
        _row(
            _decision(),
            placement_recorded_at="2026-08-25T12:00:00Z",
            placement_source="auto_dayclose",
            entry_rank=7,
            entry_count=9000,
            finish_percentile=7 / 9000,
            placement_metadata_json={"cracked_captured_board": True},
        ),
        _row(
            _decision(reason="team_balance_within_margin"),
            placement_recorded_at="2026-08-25T12:00:00Z",
            placement_source="auto_dayclose",
            placement_metadata_json={
                "cracked_captured_board": False,
                "finish_percentile_floor": 21 / 9000,
            },
        ),
        _row(_decision(reason="metadata_incomplete")),
        _row(
            _decision(),
            placement_recorded_at="2026-08-18T12:00:00Z",
            placement_source="auto_dayclose",
            entry_rank=21,
            entry_count=20,
            finish_percentile=1.05,
        ),
    ]

    coverage = analytics.summarize_rows(rows)["placement_coverage"]["versioned_stack_decisions"]

    assert coverage == {
        "total": 4,
        "exact": 1,
        "censored": 1,
        "unknown": 2,
        "measured_coverage_rate": 0.5,
    }
    assert "loss" not in json.dumps(coverage).lower()


def test_public_database_url_requires_verified_tls() -> None:
    analytics = _load_script()

    analytics._require_verified_tls(
        "postgresql://user:secret@example.invalid/database?sslmode=verify-full"
    )
    analytics._require_verified_tls(
        "postgresql://user:secret@example.invalid/database?sslmode=verify-ca"
    )
    with pytest.raises(ValueError, match="verify-ca or verify-full"):
        analytics._require_verified_tls(
            "postgresql://user:secret@example.invalid/database?sslmode=require"
        )
    with pytest.raises(ValueError, match="verify-ca or verify-full"):
        analytics._require_verified_tls("postgresql://user:secret@example.invalid/database")


def test_connection_configuration_is_read_only_and_bounded() -> None:
    analytics = _load_script()

    assert "default_transaction_read_only=on" in analytics.TRANSACTION_OPTIONS
    assert "statement_timeout=" in analytics.TRANSACTION_OPTIONS
    assert "lock_timeout=" in analytics.TRANSACTION_OPTIONS
    assert "idle_in_transaction_session_timeout=" in analytics.TRANSACTION_OPTIONS
    query = str(analytics.ANALYTICS_QUERY)
    assert "latest_freezes" in query
    assert "latest_placements" in query
    assert "DISTINCT ON (slate_date)" in query


def test_objective_sacrifice_statistics_exclude_missing_and_invalid_values() -> None:
    analytics = _load_script()
    rows = [
        _row(_decision(objective_sacrifice=0.0)),
        _row(_decision(objective_sacrifice=0.02)),
        _row(_decision(objective_sacrifice=0.04)),
        _row(_decision(objective_sacrifice=-1.0)),
        _row(_decision(objective_sacrifice=None)),
    ]

    stats = analytics.summarize_rows(rows)["decisions"]["objective_sacrifice"]

    assert stats["observed"] == 3
    assert stats["missing_or_invalid"] == 2
    assert stats["positive"] == 2
    assert stats["positive_rate"] == pytest.approx(2 / 3)
    assert stats["mean"] == pytest.approx(0.02)
    assert stats["median"] == pytest.approx(0.02)
    assert stats["minimum"] == 0.0
    assert stats["maximum"] == 0.04


def test_rollups_segment_reasons_and_composition_by_slate_size() -> None:
    analytics = _load_script()
    rows = [
        _row(_decision(slate_game_count=1, reason="best_projected_balanced")),
        _row(_decision(slate_game_count=2, reason="team_balance_within_margin")),
        _row(
            _decision(
                slate_game_count=2,
                reason="contextual_ev_override",
                selected_game_count=1,
            )
        ),
        _row(_decision(slate_game_count=4, reason="game_balance_within_margin")),
        _row(_decision(slate_game_count=None, reason="metadata_incomplete")),
    ]

    rollups = analytics.summarize_rows(rows)["decisions"]["rollups"]["slate_size"]

    assert set(rollups) == {"one_game", "two_games", "three_plus_games", "unknown"}
    assert rollups["two_games"]["rows"] == 2
    assert rollups["two_games"]["reasons"]["contextual_ev_override"]["rate"] == 0.5
    assert rollups["two_games"]["composition"]["preferred"] == 1
    assert rollups["two_games"]["composition"]["concentrated"] == 1
    assert "placement_coverage" not in json.dumps(rollups)


def test_rollups_segment_decisions_by_calendar_month() -> None:
    analytics = _load_script()
    rows = [
        _row(_decision(reason="best_projected_balanced"), slate_date="2026-08-01"),
        _row(_decision(reason="team_balance_within_margin"), slate_date="2026-08-31"),
        _row(_decision(reason="contextual_ev_override"), slate_date="2026-09-01"),
        _row(_decision(reason="metadata_incomplete"), slate_date="not-a-date"),
    ]

    months = analytics.summarize_rows(rows)["decisions"]["rollups"]["calendar_month"]

    assert set(months) == {"2026-08", "2026-09", "unknown"}
    assert months["2026-08"]["rows"] == 2
    assert months["2026-08"]["reasons"]["best_projected_balanced"]["rate"] == 0.5
    assert months["2026-09"]["reasons"]["contextual_ev_override"]["rate"] == 1.0


def test_fetch_uses_one_verified_read_only_repeatable_read_transaction() -> None:
    analytics = _load_script()
    connection = MagicMock()
    connection.execution_options.return_value = connection
    connection.begin.return_value.__enter__.return_value = connection
    set_result = MagicMock()
    read_only_result = MagicMock()
    read_only_result.scalar_one.return_value = "on"
    isolation_result = MagicMock()
    isolation_result.scalar_one.return_value = "repeatable read"
    query_result: list = []
    connection.execute.side_effect = [
        set_result,
        read_only_result,
        isolation_result,
        query_result,
    ]
    engine = MagicMock()
    engine.connect.return_value = connection

    assert analytics.fetch_rows(engine) == []

    connection.execution_options.assert_called_once_with(isolation_level="REPEATABLE READ")
    connection.begin.assert_called_once_with()
    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert statements[:3] == [
        "SET TRANSACTION READ ONLY",
        "SHOW transaction_read_only",
        "SHOW transaction_isolation",
    ]
    assert "FROM frozen_lineups" in statements[3]
    connection.close.assert_called_once_with()


def test_main_redacts_connection_errors(monkeypatch, capsys) -> None:
    analytics = _load_script()
    secret = "do-not-print-this-password"
    monkeypatch.delenv("DATABASE_PUBLIC_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        f"postgresql://user:{secret}@example.invalid/database",
    )

    def fail_create_engine(*args, **kwargs):
        del args, kwargs
        raise RuntimeError(f"raw provider error containing {secret}")

    monkeypatch.setattr(analytics, "create_engine", fail_create_engine)

    assert analytics.main([]) == 1
    captured = capsys.readouterr()
    assert secret not in captured.err
    assert "raw provider error" not in captured.err
    assert captured.err.strip() == "ERROR: stacking analytics query failed; details redacted"
