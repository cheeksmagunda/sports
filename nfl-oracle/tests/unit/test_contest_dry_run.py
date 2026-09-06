"""Offline contest dry-run: five-card shadow slate + hard-deny submit."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nfl_oracle.labels.extract import load_labels_from_corpus_root
from nfl_oracle.labels.schema import ValueLabel
from nfl_oracle.service.app import create_app
from nfl_oracle.strategy.dry_run import (
    _parse_event_date,
    build_offline_contest_dry_run,
    default_value_label_fixture_root,
    pick_decision_slate,
    prove_submit_hard_denied,
    resolve_dry_run_schedule_slate,
    select_five_card_set,
)
from nfl_oracle.strategy.dry_run_cli import main as dry_run_main
from nfl_oracle.strategy.schema import FiveCardAction

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "value_labels"
OFFLINE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "offline_research"


def test_default_fixture_root_points_at_value_labels() -> None:
    root = default_value_label_fixture_root()
    assert root.name == "value_labels"
    assert (root / "2025" / "5001" / "stats.json").is_file()


def test_pick_decision_slate_prefers_latest_five_player_game() -> None:
    labels = load_labels_from_corpus_root(FIXTURE_ROOT)
    slate = pick_decision_slate(labels)
    assert slate.season == 2025
    assert slate.game_id == 5001
    assert len(slate.players) == 5
    ids = {row.player_id for row in slate.players}
    assert ids == {501, 502, 503, 504, 505}


def test_select_five_card_set_ranks_by_value() -> None:
    players = [
        ValueLabel(player_id=1, game_id=1, season=2025, position="QB", value=1.0),
        ValueLabel(player_id=2, game_id=1, season=2025, position="RB", value=2.0),
        ValueLabel(player_id=3, game_id=1, season=2025, position="WR", value=3.0),
        ValueLabel(player_id=4, game_id=1, season=2025, position="TE", value=4.0),
        ValueLabel(player_id=5, game_id=1, season=2025, position="K", value=5.0),
        ValueLabel(player_id=6, game_id=1, season=2025, position="DEF", value=0.1),
    ]
    values = {1: 1.0, 2: 9.0, 3: 8.0, 4: 7.0, 5: 6.0, 6: 0.1}
    assert select_five_card_set(players, values) == (2, 3, 4, 5, 1)


def test_prove_submit_hard_denied() -> None:
    proof = prove_submit_hard_denied(FiveCardAction(player_ids=(1, 2, 3, 4, 5)))
    assert proof["submit_attempted"] is True
    assert proof["submit_denied"] is True
    assert proof["contest_entry"] is False
    assert "contest_entry_forbidden" in proof["submit_error"]


def test_build_offline_contest_dry_run_priors_path() -> None:
    payload = build_offline_contest_dry_run(
        corpus_root=FIXTURE_ROOT,
        use_feature_ridge=False,
        top_k_orderings=3,
    )
    assert payload["dry_run"] is True
    assert payload["observation_only"] is True
    assert payload["mode"] == "dry_run"
    assert payload["contest_entry"] is False
    assert payload["submit_enabled"] is False
    assert payload["value_source"] == "player_position_prior"
    assert payload["use_feature_ridge"] is False
    assert payload["decision_season"] == 2025
    assert payload["decision_game_id"] == 5001
    assert len(payload["five_card_set"]) == 5
    assert set(payload["five_card_set"]) == {501, 502, 503, 504, 505}
    assert payload["best_ordering"]["dry_run"] is True
    assert payload["best_ordering"]["observation_only"] is True
    assert payload["best_ordering"]["contest_entry"] is False
    assert payload["submit_proof"]["submit_denied"] is True
    assert payload["entry_gates"]["contest_entry"] is False
    assert len(payload["rankings"]) == 3
    # Highest prior should tend toward QB slot 0 under observed multipliers.
    assert payload["best_ordering"]["total"] > 0


def test_build_offline_contest_dry_run_feature_ridge() -> None:
    payload = build_offline_contest_dry_run(
        corpus_root=FIXTURE_ROOT,
        use_feature_ridge=True,
        top_k_orderings=2,
    )
    assert payload["dry_run"] is True
    assert payload["observation_only"] is True
    assert payload["contest_entry"] is False
    assert payload["value_source"] == "feature_ridge"
    assert payload["use_feature_ridge"] is True
    assert payload["value_model"]["value_source"] == "feature_ridge"
    assert payload["value_model"]["n_train_labels"] >= 1
    assert len(payload["five_card_set"]) == 5
    assert payload["submit_proof"]["submit_denied"] is True


def test_dry_run_rejects_empty_labels() -> None:
    with pytest.raises(ValueError, match="no_labels"):
        build_offline_contest_dry_run(labels=[])


def test_dry_run_cli_json(capsys: pytest.CaptureFixture[str]) -> None:
    rc = dry_run_main(["--root", str(FIXTURE_ROOT), "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"dry_run": true' in out
    assert '"observation_only": true' in out
    assert '"mode": "dry_run"' in out
    assert '"contest_entry": false' in out


def test_dry_run_cli_text_and_feature_ridge(capsys: pytest.CaptureFixture[str]) -> None:
    rc = dry_run_main(["--root", str(FIXTURE_ROOT), "--text", "--feature-ridge", "--top-k", "2"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "observation_only / dry_run" in out
    assert "value_source=feature_ridge" in out
    assert "submit_denied=True" in out


def test_research_contest_dry_run_endpoint() -> None:
    client = TestClient(create_app(project_root=OFFLINE_ROOT))
    resp = client.get("/research/shadow/contest-dry-run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True
    assert body["observation_only"] is True
    assert body["mode"] == "dry_run"
    assert body["contest_entry"] is False
    assert body["submit_proof"]["submit_denied"] is True
    assert len(body["five_card_set"]) == 5

    ridge = client.get(
        "/research/shadow/contest-dry-run",
        params={"use_feature_ridge": "true", "top_k": 3},
    )
    assert ridge.status_code == 200
    rbody = ridge.json()
    assert rbody["value_source"] == "feature_ridge"
    assert rbody["dry_run"] is True
    assert rbody["contest_entry"] is False


def test_parse_event_date_iso_z() -> None:
    assert _parse_event_date("2025-09-07T17:00:00.000Z").isoformat() == "2025-09-07"
    assert _parse_event_date("2024-09-05") is not None
    assert _parse_event_date(None) is None
    assert _parse_event_date("not-a-date") is None


def test_resolve_dry_run_schedule_slate_priority() -> None:
    from datetime import date

    offline = OFFLINE_ROOT
    labels = load_labels_from_corpus_root(FIXTURE_ROOT)
    slate = pick_decision_slate(labels)
    # Explicit week wins over label event_time.
    by_week = resolve_dry_run_schedule_slate(
        decision_season=slate.season,
        slate_players=slate.players,
        schedule_week=2,
        project_root=offline,
    )
    assert by_week["dry_run_attach"]["source"] == "explicit_schedule_week"
    assert by_week["week"] == 2
    assert by_week["contest_entry"] is False
    # Explicit date wins.
    by_date = resolve_dry_run_schedule_slate(
        decision_season=slate.season,
        slate_players=slate.players,
        schedule_date=date(2024, 9, 5),
        schedule_team="KC",
        project_root=offline,
    )
    assert by_date["dry_run_attach"]["source"] == "explicit_schedule_date"
    assert by_date["resolve_mode"] == "date_exact_gameday"
    assert by_date["team_opponent"] == "BAL"
    # Label event_time when no explicit week/date (2025-09-07 → week 1).
    by_event = resolve_dry_run_schedule_slate(
        decision_season=slate.season,
        slate_players=slate.players,
        project_root=offline,
    )
    assert by_event["dry_run_attach"]["source"] == "label_event_time"
    assert by_event["resolved"] is True
    assert by_event["week"] == 1
    assert by_event["season"] == 2025
    # Fallback week-1 when labels lack event_time.
    bare = [
        ValueLabel(player_id=1, game_id=1, season=2024, position="QB", value=1.0),
        ValueLabel(player_id=2, game_id=1, season=2024, position="RB", value=1.0),
        ValueLabel(player_id=3, game_id=1, season=2024, position="WR", value=1.0),
        ValueLabel(player_id=4, game_id=1, season=2024, position="TE", value=1.0),
        ValueLabel(player_id=5, game_id=1, season=2024, position="K", value=1.0),
    ]
    fallback = resolve_dry_run_schedule_slate(
        decision_season=2024,
        slate_players=bare,
        project_root=offline,
    )
    assert fallback["dry_run_attach"]["source"] == "default_week_1_fallback"
    assert fallback["week"] == 1
    assert fallback["contest_entry"] is False


def test_dry_run_optional_schedule_slate_attachment() -> None:
    from datetime import date

    offline = OFFLINE_ROOT
    payload = build_offline_contest_dry_run(
        corpus_root=FIXTURE_ROOT,
        include_schedule_slate=True,
        schedule_week=1,
        project_root=offline,
    )
    assert payload["schedule_slate"] is not None
    assert payload["schedule_slate"]["contest_entry"] is False
    assert payload["schedule_slate"]["resolved"] is True
    assert payload["schedule_slate"]["dry_run_attach"]["source"] == "explicit_schedule_week"
    assert payload["contest_entry"] is False
    by_date = build_offline_contest_dry_run(
        corpus_root=FIXTURE_ROOT,
        include_schedule_slate=True,
        schedule_date=date(2024, 9, 5),
        project_root=offline,
    )
    assert by_date["schedule_slate"]["resolve_mode"] == "date_exact_gameday"
    assert by_date["schedule_slate"]["dry_run_attach"]["source"] == "explicit_schedule_date"
    # Auto-resolve from fixture label event_time (no week/date args).
    auto = build_offline_contest_dry_run(
        corpus_root=FIXTURE_ROOT,
        include_schedule_slate=True,
        project_root=offline,
    )
    assert auto["schedule_slate"]["dry_run_attach"]["source"] == "label_event_time"
    assert auto["schedule_slate"]["resolved"] is True
    assert auto["contest_entry"] is False
    plain = build_offline_contest_dry_run(corpus_root=FIXTURE_ROOT)
    assert plain["schedule_slate"] is None


def test_dry_run_cli_include_schedule_slate(capsys: pytest.CaptureFixture[str]) -> None:
    rc = dry_run_main(
        [
            "--root",
            str(FIXTURE_ROOT),
            "--text",
            "--include-schedule-slate",
            "--project-root",
            str(OFFLINE_ROOT),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "schedule_slate=resolved=True" in out
    assert "source=label_event_time" in out
