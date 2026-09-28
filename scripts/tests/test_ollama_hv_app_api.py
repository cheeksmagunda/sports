"""Offline tests: pregame leak stop + sport app API adapter + daemon (#574).

HTTP is mocked by monkeypatching ``urllib.request.urlopen``. Payload shapes
mirror nfl-oracle ``recommendations/app.py`` and wnba-oracle ``api/slate.py``
/ ``api/lineup.py`` (confirmed by live GET). Days and players are synthetic.
"""

from __future__ import annotations

import copy
import io
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from ollama_hv_watcher import learn as learn_mod
from ollama_hv_watcher.adapters import app_api
from ollama_hv_watcher.app_daemon import AppDaemonConfig, run_app_daemon
from ollama_hv_watcher.boards import (
    armed_board_paths,
    load_history_board_summary,
    load_pregame_board_summary,
    summarize_board_payload,
)
from ollama_hv_watcher.cli import main as cli_main
from ollama_hv_watcher.learn import build_learn_prompt
from ollama_hv_watcher.live import LiveDataRequiredError
from ollama_hv_watcher.pick import five_player_lineup, frozen_app_lineup
from ollama_hv_watcher.windows import SlateWindow, load_windows_payload

DAY = "2000-01-02"
NFL_BASE = "https://nfl.example.invalid"
WNBA_BASE = "https://wnba.example.invalid"
ENV = {
    "SPORTS_OLLAMA_NFL_API_URL": NFL_BASE,
    "SPORTS_OLLAMA_WNBA_API_URL": WNBA_BASE,
}
FIXTURE_BOARD = SCRIPTS / "ollama_hv_watcher" / "fixtures" / "hv_board_sample.json"


def _no_sleep(_s: float) -> None:
    return None


# --------------------------------------------------------------- payloads


def _nfl_pick(i: int) -> dict[str, Any]:
    return {
        "player_id": 1000 + i,
        "game_id": 77,
        "team_id": 1,
        "name": f"Nfl Player {i}",
        "position": "WR",
        "team": "AAA",
        "opponent": "BBB",
        "slot": i,
        "slot_multiplier": [2.0, 1.8, 1.6, 1.4, 1.2][i - 1],
        "card_boost": 1.0,
        # Deliberately NOT sorted by value: the app's slot order must win.
        "projected_value": [2.0, 3.5, 1.0, 2.5, 0.5][i - 1],
        "projected_score": 8.0,
        "uncertainty": 1.2,
        "ownership": 0.1,
        "ownership_source": "estimated_projection_softmax",
    }


def nfl_waiting() -> dict[str, Any]:
    return {
        "slate_date": DAY,
        "server_time": "2000-01-02T07:34:36+00:00",
        "contest_entry": False,
        "lineup": None,
        "games": [],
        "run": {
            "status": "waiting",
            "detail_code": "waiting_offline_pregate",
            "checked_at": "2000-01-02T07:34:34+00:00",
            "details": {
                "gate_source": "offline_schedule",
                "next_live_check_by": "2000-01-02T16:00:00+00:00",
                "cutoff_at": "2000-01-02T17:00:00+00:00",
            },
        },
        "status": "waiting",
        "stale": False,
        "next_freeze": None,
    }


def nfl_frozen() -> dict[str, Any]:
    return {
        "slate_date": DAY,
        "server_time": "2000-01-02T16:30:00+00:00",
        "contest_entry": False,
        "lineup": {
            "picks": [_nfl_pick(i) for i in range(1, 6)],
            "objective": "total_value",
            "total_value": 40.0,
            "boost_regime": "provider_boosts_present",
        },
        "games": [
            {
                "game_id": 77,
                "kickoff_at": "2000-01-02T17:00:00Z",
                "home_team": "AAA",
                "away_team": "BBB",
                "status": "scheduled",
            },
            {
                "game_id": 78,
                "kickoff_at": "2000-01-03T00:20:00Z",
                "home_team": "CCC",
                "away_team": "DDD",
                "status": "scheduled",
            },
        ],
        "run": {"status": "ready", "checked_at": "2000-01-02T16:20:05+00:00"},
        "status": "frozen",
        "stale": False,
        "cutoff_at": "2000-01-02T17:00:00+00:00",
        "frozen_at": "2000-01-02T16:20:04+00:00",
        "sequence": 1,
        "digest": "d" * 64,
        "model_fingerprint": "m" * 64,
        "input_fingerprint": "i" * 64,
    }


def wnba_slate() -> dict[str, Any]:
    return {
        "slate_date": DAY,
        "first_tip_utc": "2000-01-02T18:00:00+00:00",
        "contest_lock_utc": None,
        "freeze_lead_minutes": 40,
        "freeze_target_utc": "2000-01-02T17:20:00+00:00",
        "picks_paused": False,
        "resumes_on": None,
    }


def _wnba_player(i: int) -> dict[str, Any]:
    return {
        "team": "IND",
        "game_id": "11746" + str(i),
        "opponent": "MIN",
        "position": "G",
        "archetype": "ceiling_anchor",
        "player_id": 600 + i,
        "card_boost": 0.5,
        "display_name": f"Wnba Player {i}",
        "stat_leverage": 0.2,
        "pred_minutes_p50": 30.0,
        "pred_real_score_p10": 1.0,
        "pred_real_score_p50": 5.0 - i * 0.5,
        "pred_real_score_p90": 8.0,
    }


def wnba_lineup() -> dict[str, Any]:
    players = [_wnba_player(i) for i in range(1, 6)]
    return {
        "slate_date": DAY,
        "model_sha": "7" * 64,
        "payout_regime": "top_20",
        "frozen_at": "2000-01-02T17:20:35.241070+00:00",
        "lineup": {
            "per_player": players,
            "player_ids": [p["player_id"] for p in players],
            "slot_multipliers": [2.0, 1.8, 1.6, 1.4, 1.2],
            "lineup_score_p50": 43.3,
        },
        "entry_recommendation": "enter",
        "expected_payout": 1.8,
        "metadata_json": {"frozen_via": "job2_first_fire"},
        "freeze_seq": 1,
        "frozen_via": "job2_first_fire",
        "n_freezes": 1,
    }


# ------------------------------------------------------------ HTTP mock


class _Resp(io.BytesIO):
    status = 200

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class FakeHttp:
    """Route table: url -> payload | int (HTTP error code) | Exception."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    def __call__(self, req: Any, timeout: float | None = None) -> _Resp:
        url = req.full_url if hasattr(req, "full_url") else str(req)
        assert timeout is not None and timeout > 0
        self.calls.append(url)
        route = self.routes.get(url, 404)
        if isinstance(route, list):
            route = route.pop(0) if len(route) > 1 else route[0]
        if isinstance(route, BaseException):
            raise route
        if isinstance(route, int):
            raise urllib.error.HTTPError(url, route, "err", {}, None)  # type: ignore[arg-type]
        return _Resp(json.dumps(route).encode("utf-8"))


@pytest.fixture
def http(monkeypatch: pytest.MonkeyPatch) -> FakeHttp:
    fake = FakeHttp({})
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return fake


# ------------------------------------------------------- 1. leak stop


def _pregame_board(**over: Any) -> dict[str, Any]:
    board = {
        "sport": "nfl",
        "slate_key": DAY,
        "label": "x",
        "section": "app_frozen_lineup",
        "phase": "pregame",
        "players": [
            {"player_id": i, "name": f"P{i}", "value": 10.0 - i, "slot": i}
            for i in range(1, 6)
        ],
    }
    board.update(over)
    return board


def test_pregame_board_requires_phase_pregame() -> None:
    board = _pregame_board()
    board.pop("phase")
    with pytest.raises(LiveDataRequiredError, match="phase"):
        summarize_board_payload(board, mode="pregame")


def test_pregame_board_refuses_final_game_status() -> None:
    with pytest.raises(LiveDataRequiredError, match="game_status"):
        summarize_board_payload(_pregame_board(game_status="final"), mode="pregame")


@pytest.mark.parametrize("leak", ["real_score", "score", "actual_points", "Actual"])
def test_pregame_board_refuses_outcome_fields(leak: str) -> None:
    board = _pregame_board()
    board["players"][2][leak] = 12.5
    with pytest.raises(LiveDataRequiredError, match="outcome fields"):
        summarize_board_payload(board, mode="pregame")


def test_pregame_prompt_and_lineup_never_emit_real_score() -> None:
    summary = summarize_board_payload(_pregame_board(), mode="pregame")
    assert summary.is_pregame
    card = five_player_lineup(summary)
    assert all("real_score" not in row for row in card)
    assert all("real_score" not in row for row in summary.top_players)
    assert "real_score" not in summary.prompt_block()
    assert "real_score" not in build_learn_prompt(summary)


def test_history_board_is_explicit_path_only(tmp_path: Path) -> None:
    summary = load_history_board_summary(FIXTURE_BOARD)
    assert summary.phase == "history"
    assert "real_score" in five_player_lineup(summary)[0]
    with pytest.raises(LiveDataRequiredError):
        load_pregame_board_summary(FIXTURE_BOARD)


def test_live_discovery_only_armed_slate_dirs(tmp_path: Path) -> None:
    hist = tmp_path / "boards" / "nfl" / "hv_board.json"
    hist.parent.mkdir(parents=True)
    hist.write_text(FIXTURE_BOARD.read_text(encoding="utf-8"), encoding="utf-8")
    armed = tmp_path / "nfl" / DAY / "hv_board.json"
    armed.parent.mkdir(parents=True)
    armed.write_text(json.dumps(_pregame_board()), encoding="utf-8")
    other = tmp_path / "wnba" / DAY / "hv_board.json"
    other.parent.mkdir(parents=True)
    other.write_text(json.dumps(_pregame_board(sport="wnba")), encoding="utf-8")
    slate = SlateWindow(
        sport="nfl",
        slate_id=DAY,
        freeze_or_kickoff_at=datetime(2000, 1, 2, 17, tzinfo=UTC),
        close_at=datetime(2000, 1, 2, 21, tzinfo=UTC),
    )
    assert armed_board_paths(tmp_path, [slate]) == [armed]


# ---------------------------------------------------------- 2. adapter


def test_missing_env_url_fails_closed() -> None:
    with pytest.raises(LiveDataRequiredError, match="SPORTS_OLLAMA_NFL_API_URL"):
        app_api.slate_window("nfl", DAY, environ={})
    with pytest.raises(LiveDataRequiredError, match="SPORTS_OLLAMA_WNBA_API_URL"):
        app_api.frozen_board("wnba", DAY, environ={}, data_root=None)


def test_unknown_sport_refused() -> None:
    with pytest.raises(LiveDataRequiredError, match="no app API adapter"):
        app_api.slate_window("cricket", DAY, environ=ENV)


def test_nfl_window_before_freeze_uses_run_cutoff(http: FakeHttp) -> None:
    http.routes[f"{NFL_BASE}/slate/{DAY}"] = nfl_waiting()
    w = app_api.slate_window("nfl", DAY, environ=ENV, sleep_fn=_no_sleep)
    assert w.session_id == f"nfl:{DAY}"
    assert w.freeze_or_kickoff_at == datetime(2000, 1, 2, 17, tzinfo=UTC)
    assert w.arm_at == datetime(2000, 1, 2, 16, 20, tzinfo=UTC)
    assert w.close_at == datetime(2000, 1, 2, 21, tzinfo=UTC)


def test_nfl_window_after_freeze_closes_after_last_kickoff(http: FakeHttp) -> None:
    payload = nfl_frozen()
    payload.pop("lineup")  # /slate drops the lineup
    http.routes[f"{NFL_BASE}/slate/{DAY}"] = payload
    w = app_api.slate_window("nfl", DAY, environ=ENV, sleep_fn=_no_sleep)
    # last kickoff 00:20Z + 3h + 1h (nfl-oracle week_close constants)
    assert w.close_at == datetime(2000, 1, 3, 4, 20, tzinfo=UTC)


def test_nfl_window_missing_cutoff_fails_closed(http: FakeHttp) -> None:
    payload = nfl_waiting()
    payload["run"]["details"].pop("cutoff_at")
    http.routes[f"{NFL_BASE}/slate/{DAY}"] = payload
    with pytest.raises(LiveDataRequiredError, match="cutoff_at"):
        app_api.slate_window("nfl", DAY, environ=ENV, sleep_fn=_no_sleep)


def test_nfl_not_yet_frozen_is_none(http: FakeHttp, tmp_path: Path) -> None:
    http.routes[f"{NFL_BASE}/lineup/{DAY}"] = nfl_waiting()
    assert app_api.frozen_board("nfl", DAY, environ=ENV, data_root=tmp_path) is None
    assert not (tmp_path / "nfl" / DAY / "hv_board.json").exists()


def test_nfl_frozen_board_parses_app_five(http: FakeHttp, tmp_path: Path) -> None:
    http.routes[f"{NFL_BASE}/lineup/{DAY}"] = nfl_frozen()
    board = app_api.frozen_board("nfl", DAY, environ=ENV, data_root=tmp_path)
    assert board is not None
    assert board["phase"] == "pregame"
    assert board["section"] == "app_frozen_lineup"
    assert board["slate_key"] == DAY
    assert board["frozen_at"] == "2000-01-02T16:20:04Z"
    assert [p["slot"] for p in board["players"]] == [1, 2, 3, 4, 5]
    assert [p["value"] for p in board["players"]] == [2.0, 3.5, 1.0, 2.5, 0.5]
    assert board["players"][0]["card_boost"] == 1.0
    assert board["players"][0]["slot_multiplier"] == 2.0
    written = tmp_path / "nfl" / DAY / "hv_board.json"
    assert json.loads(written.read_text(encoding="utf-8")) == board
    assert not list(written.parent.glob("*.tmp"))
    # The written board passes the live leak stop and keeps the app's order.
    summary = load_pregame_board_summary(written)
    card = frozen_app_lineup(summary)
    assert [r["name"] for r in card] == [f"Nfl Player {i}" for i in range(1, 6)]


@pytest.mark.parametrize("count", [4, 6])
def test_nfl_not_five_picks_refused(http: FakeHttp, count: int) -> None:
    payload = nfl_frozen()
    payload["lineup"]["picks"] = [_nfl_pick(1 + (i % 5)) for i in range(count)]
    http.routes[f"{NFL_BASE}/lineup/{DAY}"] = payload
    with pytest.raises(LiveDataRequiredError, match="need exactly 5"):
        app_api.frozen_board("nfl", DAY, environ=ENV, data_root=None)


def test_nfl_stale_freeze_refused(http: FakeHttp) -> None:
    payload = nfl_frozen()
    payload["stale"] = True
    http.routes[f"{NFL_BASE}/lineup/{DAY}"] = payload
    with pytest.raises(LiveDataRequiredError, match="stale"):
        app_api.frozen_board("nfl", DAY, environ=ENV, data_root=None)


def test_nfl_wrong_day_refused(http: FakeHttp) -> None:
    payload = nfl_frozen()
    payload["slate_date"] = "2000-01-09"
    http.routes[f"{NFL_BASE}/lineup/{DAY}"] = payload
    with pytest.raises(LiveDataRequiredError, match="slate_date"):
        app_api.frozen_board("nfl", DAY, environ=ENV, data_root=None)


def test_wnba_window_uses_app_freeze_target(http: FakeHttp) -> None:
    http.routes[f"{WNBA_BASE}/slate/{DAY}"] = wnba_slate()
    w = app_api.slate_window("wnba", DAY, environ=ENV, sleep_fn=_no_sleep)
    assert w.arm_at == datetime(2000, 1, 2, 17, 20, tzinfo=UTC)
    assert w.lead_minutes == 40
    assert w.close_at == datetime(2000, 1, 3, 0, 0, tzinfo=UTC)


def test_wnba_window_404_and_paused_fail_closed(http: FakeHttp) -> None:
    with pytest.raises(LiveDataRequiredError, match="404"):
        app_api.slate_window("wnba", DAY, environ=ENV, sleep_fn=_no_sleep)
    paused = wnba_slate()
    paused.update(picks_paused=True, first_tip_utc=None, freeze_target_utc=None)
    http.routes[f"{WNBA_BASE}/slate/{DAY}"] = paused
    with pytest.raises(LiveDataRequiredError, match="picks_paused"):
        app_api.slate_window("wnba", DAY, environ=ENV, sleep_fn=_no_sleep)


def test_wnba_not_yet_frozen_404_is_none(http: FakeHttp) -> None:
    assert app_api.frozen_board("wnba", DAY, environ=ENV, data_root=None) is None


def test_wnba_frozen_board_parses_per_player(http: FakeHttp) -> None:
    http.routes[f"{WNBA_BASE}/lineup/{DAY}"] = wnba_lineup()
    board = app_api.frozen_board("wnba", DAY, environ=ENV, data_root=None)
    assert board is not None
    assert [p["name"] for p in board["players"]] == [
        f"Wnba Player {i}" for i in range(1, 6)
    ]
    assert [p["slot_multiplier"] for p in board["players"]] == [
        2.0,
        1.8,
        1.6,
        1.4,
        1.2,
    ]
    assert board["players"][0]["value"] == 4.5
    assert board["players"][0]["value_field"] == "pred_real_score_p50"
    # Projections are renamed so no key can be mistaken for an outcome.
    assert all("real_score" not in k for p in board["players"] for k in p)
    summary = summarize_board_payload(board, mode="pregame")
    assert summary.player_count == 5


def test_wnba_six_players_refused(http: FakeHttp) -> None:
    payload = wnba_lineup()
    payload["lineup"]["per_player"].append(_wnba_player(6))
    payload["lineup"]["player_ids"].append(606)
    http.routes[f"{WNBA_BASE}/lineup/{DAY}"] = payload
    with pytest.raises(LiveDataRequiredError, match="need exactly 5"):
        app_api.frozen_board("wnba", DAY, environ=ENV, data_root=None)


def test_get_json_retries_5xx_then_succeeds(http: FakeHttp) -> None:
    url = f"{WNBA_BASE}/slate/{DAY}"
    http.routes[url] = [503, wnba_slate()]
    slept: list[float] = []
    w = app_api.slate_window("wnba", DAY, environ=ENV, sleep_fn=slept.append)
    assert w.lead_minutes == 40
    assert http.calls.count(url) == 2
    assert slept == [1.0]


def test_get_json_gives_up_after_bounded_attempts(http: FakeHttp) -> None:
    url = f"{NFL_BASE}/slate/{DAY}"
    http.routes[url] = [urllib.error.URLError("down")]
    with pytest.raises(app_api.AppApiUnavailableError, match="attempts=3"):
        app_api.slate_window("nfl", DAY, environ=ENV, sleep_fn=_no_sleep)
    assert http.calls.count(url) == app_api.DEFAULT_ATTEMPTS


# ------------------------------------------------ 3. daemon + windows CLI


def test_daemon_ollama_unavailable_still_records_app_five(
    http: FakeHttp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    http.routes[f"{NFL_BASE}/slate/{DAY}"] = nfl_waiting()
    http.routes[f"{NFL_BASE}/lineup/{DAY}"] = [nfl_waiting(), nfl_frozen()]

    def down(*_a: Any, **_k: Any) -> str:
        raise RuntimeError("ollama_generate_failed:<urlopen error refused>")

    monkeypatch.setattr(learn_mod, "generate", down)
    events: list[dict[str, Any]] = []
    cfg = AppDaemonConfig(
        day=DAY,
        sports=("nfl",),
        data_root=tmp_path,
        execute=True,
        poll_seconds=1.0,
        environ={**ENV, "SPORTS_OLLAMA_UNLOCK": "1"},
    )
    result = run_app_daemon(
        cfg,
        now_fn=lambda: datetime(2000, 1, 2, 16, 25, tzinfo=UTC),
        sleep_fn=_no_sleep,
        emit=events.append,
        max_iterations=3,
    )
    assert any(e["event"] == "waiting_for_app_freeze" for e in events)
    assert len(result["ticks"]) == 1  # one tick per app freeze, no repeats
    tick = json.loads(Path(result["ticks"][0]).read_text(encoding="utf-8"))
    assert tick["notes"] == "ollama_unavailable"
    assert tick["lineup_source"] == "app_frozen_lineup"
    assert tick["phase"] == "pregame"
    app_five = [p["player_id"] for p in nfl_frozen()["lineup"]["picks"]]
    assert [r["player_id"] for r in tick["five_player_lineup"]] == app_five
    assert [r["slot"] for r in tick["five_player_lineup"]] == [1, 2, 3, 4, 5]
    assert "real_score" not in json.dumps(tick)


def test_daemon_does_not_tick_before_arm(http: FakeHttp, tmp_path: Path) -> None:
    http.routes[f"{NFL_BASE}/slate/{DAY}"] = nfl_waiting()
    http.routes[f"{NFL_BASE}/lineup/{DAY}"] = nfl_frozen()
    cfg = AppDaemonConfig(
        day=DAY, sports=("nfl",), data_root=tmp_path, environ=ENV, poll_seconds=1.0
    )
    result = run_app_daemon(
        cfg,
        now_fn=lambda: datetime(2000, 1, 2, 9, 0, tzinfo=UTC),
        sleep_fn=_no_sleep,
        emit=lambda _e: None,
        max_iterations=1,
    )
    assert result["ticks"] == []
    assert f"{NFL_BASE}/lineup/{DAY}" not in http.calls


def test_windows_from_apps_cli_output_loads(
    http: FakeHttp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    http.routes[f"{NFL_BASE}/slate/{DAY}"] = nfl_waiting()
    http.routes[f"{WNBA_BASE}/slate/{DAY}"] = wnba_slate()
    code = cli_main(
        [
            "--windows-from-apps",
            "--day",
            DAY,
            "--sports",
            "nfl,wnba",
            "--data-root",
            str(tmp_path),
        ]
    )
    assert code == 0
    out = tmp_path / "windows" / f"{DAY}.json"
    plan = load_windows_payload(json.loads(out.read_text(encoding="utf-8")))
    assert {s.session_id for s in plan.slates} == {f"nfl:{DAY}", f"wnba:{DAY}"}
    assert plan.arm_at == datetime(2000, 1, 2, 16, 20, tzinfo=UTC)


def test_windows_from_apps_no_live_slate_exits_4(
    http: FakeHttp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    code = cli_main(
        ["--windows-from-apps", "--day", DAY, "--sports", "wnba"]
        + ["--data-root", str(tmp_path)]
    )
    assert code == 4
    assert not (tmp_path / "windows").exists()


def test_board_payload_is_not_mutated_by_summary() -> None:
    board = _pregame_board()
    before = copy.deepcopy(board)
    summarize_board_payload(board, mode="pregame")
    assert board == before
