"""Watchdog trigger logic — pure function tests against a mocked engine."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import pickle
from unittest.mock import MagicMock, patch

from wnba_oracle.scheduler import watchdog, watchdog_checks, watchdog_drift


def _engine_with_pool_count(
    n: int,
    n_teams: int | None = None,
    last_captured: dt.datetime | None = None,
) -> MagicMock:
    eng = MagicMock()
    result = MagicMock()
    # POOL_SIZE_Q returns (count, distinct teams, max captured_at).
    teams = n_teams if n_teams is not None else min(n, 12)
    result.first.return_value = (n, teams, last_captured)
    conn = MagicMock()
    conn.execute.return_value = result
    eng.connect.return_value.__enter__.return_value = conn
    return eng


def _engine_with_freeze_row(row: tuple | None) -> MagicMock:
    eng = MagicMock()
    result = MagicMock()
    result.first.return_value = row
    conn = MagicMock()
    conn.execute.return_value = result
    eng.connect.return_value.__enter__.return_value = conn
    return eng


def _engine_for_enrichment_check(
    n: int,
    n_teams: int | None = None,
    last_captured: dt.datetime | None = None,
    frozen_row: tuple | None = None,
) -> MagicMock:
    """`_check_enrichment_freshness` queries FROZEN_Q then POOL_SIZE_Q, in
    that order -- side_effect mirrors the two calls."""
    eng = MagicMock()
    frozen_result = MagicMock()
    frozen_result.first.return_value = frozen_row
    pool_result = MagicMock()
    teams = n_teams if n_teams is not None else min(n, 12)
    pool_result.first.return_value = (n, teams, last_captured)
    conn = MagicMock()
    conn.execute.side_effect = [frozen_result, pool_result]
    eng.connect.return_value.__enter__.return_value = conn
    return eng


def test_no_job1_pool_triggers_critical() -> None:
    with patch.object(watchdog_checks, "get_engine", return_value=_engine_with_pool_count(0)):
        events = watchdog._check_pool("2026-05-27")
    assert len(events) == 1
    assert events[0].trigger == "no_job1_pool"
    assert events[0].severity == "critical"


def test_small_pool_triggers_error() -> None:
    """D84: escalated from warn — a sub-10 pool is an ingest failure."""
    with patch.object(watchdog_checks, "get_engine", return_value=_engine_with_pool_count(7)):
        events = watchdog._check_pool("2026-05-27")
    assert len(events) == 1
    assert events[0].trigger == "pool_too_small"
    assert events[0].severity == "error"
    assert events[0].payload["pool_size"] == 7


def test_single_team_pool_triggers_critical() -> None:
    """D84: the 2026-06-08 morning shape — rows exist, one team."""
    eng = _engine_with_pool_count(12, n_teams=1)
    with patch.object(watchdog_checks, "get_engine", return_value=eng):
        events = watchdog._check_pool("2026-05-27")
    triggers = {e.trigger: e.severity for e in events}
    assert triggers.get("pool_degenerate_teams") == "critical"


def test_enrichment_stale_after_20utc() -> None:
    stale = dt.datetime(2026, 5, 27, 9, 0, tzinfo=dt.UTC)
    eng = _engine_for_enrichment_check(60, last_captured=stale, frozen_row=None)
    with patch.object(watchdog_checks, "get_engine", return_value=eng):
        events = watchdog._check_enrichment_freshness(
            "2026-05-27", now_utc=dt.datetime(2026, 5, 27, 20, 30, tzinfo=dt.UTC)
        )
    assert len(events) == 1
    assert events[0].trigger == "enrichment_stale"
    assert events[0].severity == "warn"


def test_enrichment_fresh_no_event() -> None:
    fresh = dt.datetime(2026, 5, 27, 13, 40, tzinfo=dt.UTC)
    eng = _engine_for_enrichment_check(60, last_captured=fresh, frozen_row=None)
    with patch.object(watchdog_checks, "get_engine", return_value=eng):
        events = watchdog._check_enrichment_freshness(
            "2026-05-27", now_utc=dt.datetime(2026, 5, 27, 20, 30, tzinfo=dt.UTC)
        )
    assert events == []


def test_enrichment_stale_quiet_when_already_frozen() -> None:
    """Early tip-off (D93): the slate already froze hours before 20:00 UTC
    on whatever was fresh at freeze time. The capture-recency check must not
    second-guess a freeze that already happened successfully."""
    stale = dt.datetime(2026, 8, 1, 13, 7, tzinfo=dt.UTC)
    frozen_row = ({"player_ids": [1, 2, 3]}, 1.32, dt.datetime(2026, 8, 1, 16, 22, tzinfo=dt.UTC))
    eng = _engine_for_enrichment_check(60, last_captured=stale, frozen_row=frozen_row)
    with patch.object(watchdog_checks, "get_engine", return_value=eng):
        events = watchdog._check_enrichment_freshness(
            "2026-08-01", now_utc=dt.datetime(2026, 8, 1, 20, 2, tzinfo=dt.UTC)
        )
    assert events == []


def test_enrichment_freshness_quiet_before_20utc() -> None:
    """The 13:00 UTC job1-path watchdog run must not flag the capture it
    just made (or its absence minutes before)."""
    eng = _engine_with_pool_count(60, last_captured=None)
    with patch.object(watchdog_checks, "get_engine", return_value=eng):
        events = watchdog._check_enrichment_freshness(
            "2026-05-27", now_utc=dt.datetime(2026, 5, 27, 13, 10, tzinfo=dt.UTC)
        )
    assert events == []


def _engine_with_coverage(
    n_contest: int, n_missing: int, sample: list[tuple] | None = None
) -> MagicMock:
    eng = MagicMock()
    cov_result = MagicMock()
    cov_result.first.return_value = (n_contest, n_missing)
    sample_result = iter(sample or [])
    conn = MagicMock()
    conn.execute.side_effect = [cov_result, sample_result]
    eng.connect.return_value.__enter__.return_value = conn
    return eng


def test_label_coverage_gap_warn_on_small_gap() -> None:
    eng = _engine_with_coverage(80, 2, [(726, "J. Loyd"), (627, "A. Boston")])
    with patch.object(watchdog_checks, "get_engine", return_value=eng):
        events = watchdog._check_label_coverage("2026-06-08")
    assert len(events) == 1
    assert events[0].trigger == "label_coverage_gap"
    assert events[0].severity == "warn"
    assert events[0].payload["n_missing"] == 2
    assert {s["player_id"] for s in events[0].payload["sample"]} == {726, 627}


def test_label_coverage_gap_error_above_20pct() -> None:
    eng = _engine_with_coverage(80, 40, [(1, "P1")])
    with patch.object(watchdog_checks, "get_engine", return_value=eng):
        events = watchdog._check_label_coverage("2026-06-08")
    assert events[0].severity == "error"


def test_label_coverage_clean_no_event() -> None:
    eng = _engine_with_coverage(80, 0)
    with patch.object(watchdog_checks, "get_engine", return_value=eng):
        assert watchdog._check_label_coverage("2026-06-08") == []


def test_label_coverage_quiet_on_empty_pool() -> None:
    """dayclose ingest checks own the no-leaderboard signal; coverage stays silent."""
    eng = _engine_with_coverage(0, 0)
    with patch.object(watchdog_checks, "get_engine", return_value=eng):
        assert watchdog._check_label_coverage("2026-06-08") == []


def _ev(severity: str) -> watchdog.WatchdogEvent:
    return watchdog.WatchdogEvent(
        slate_date="2026-05-27", trigger="t", severity=severity, payload={}
    )


def test_ping_fires_on_critical_when_url_set() -> None:
    from types import SimpleNamespace

    settings = SimpleNamespace(watchdog_ping_url="https://hc.example/abc")
    with (
        patch("wnba_oracle.common.settings.get_settings", return_value=settings),
        patch("oracle_core.http.request_with_retry") as request,
    ):
        request.return_value = SimpleNamespace(status_code=200)
        watchdog._ping_on_critical([_ev("critical")])
    request.assert_called_once()
    assert request.call_args.args[1:3] == ("GET", "https://hc.example/abc/fail")


def test_ping_logs_delivered_only_on_2xx_response() -> None:
    """A non-2xx response (e.g. a stale/misconfigured monitor URL) must not
    be logged as delivered: request_with_retry only raises on transport
    failures, so a 404/401/etc. response returns normally and would
    silently masquerade as a successful page without an explicit check."""
    from types import SimpleNamespace

    settings = SimpleNamespace(watchdog_ping_url="https://hc.example/abc")
    with (
        patch("wnba_oracle.common.settings.get_settings", return_value=settings),
        patch("oracle_core.http.request_with_retry") as request,
        patch.object(watchdog, "log") as log,
    ):
        request.return_value = SimpleNamespace(status_code=404)
        watchdog._ping_on_critical([_ev("critical")])
    log.warning.assert_called_once_with(
        "watchdog_ping_not_delivered", url_suffix="/fail", status_code=404
    )
    log.info.assert_not_called()


def test_ping_logs_sent_on_2xx_response() -> None:
    from types import SimpleNamespace

    settings = SimpleNamespace(watchdog_ping_url="https://hc.example/abc")
    with (
        patch("wnba_oracle.common.settings.get_settings", return_value=settings),
        patch("oracle_core.http.request_with_retry") as request,
        patch.object(watchdog, "log") as log,
    ):
        request.return_value = SimpleNamespace(status_code=200)
        watchdog._ping_on_critical([_ev("critical")])
    log.info.assert_called_once_with("watchdog_ping_sent", url_suffix="/fail")
    log.warning.assert_not_called()


def test_ping_skipped_without_critical() -> None:
    from types import SimpleNamespace

    settings = SimpleNamespace(watchdog_ping_url="https://hc.example/abc")
    with (
        patch("wnba_oracle.common.settings.get_settings", return_value=settings),
        patch("oracle_core.http.request_with_retry") as request,
    ):
        watchdog._ping_on_critical([_ev("warn"), _ev("error")])
    request.assert_not_called()


def test_ping_noop_without_url() -> None:
    from types import SimpleNamespace

    settings = SimpleNamespace(watchdog_ping_url="")
    with (
        patch("wnba_oracle.common.settings.get_settings", return_value=settings),
        patch("oracle_core.http.request_with_retry") as request,
    ):
        watchdog._ping_on_critical([_ev("critical")])
    request.assert_not_called()


def test_healthy_pool_no_events() -> None:
    with patch.object(watchdog_checks, "get_engine", return_value=_engine_with_pool_count(60)):
        assert watchdog._check_pool("2026-05-27") == []


def test_no_frozen_lineup_after_22utc_triggers_critical() -> None:
    with patch.object(watchdog_checks, "get_engine", return_value=_engine_with_freeze_row(None)):
        events = watchdog._check_freeze(
            "2026-05-27",
            now_utc=dt.datetime(2026, 5, 27, 22, 30, tzinfo=dt.UTC),
        )
    assert len(events) == 1
    assert events[0].trigger == "no_frozen_lineup"
    assert events[0].severity == "critical"


def test_no_frozen_lineup_before_22utc_no_event() -> None:
    """Quiet before the cron-job2 window has had enough attempts."""
    with patch.object(watchdog_checks, "get_engine", return_value=_engine_with_freeze_row(None)):
        events = watchdog._check_freeze(
            "2026-05-27",
            now_utc=dt.datetime(2026, 5, 27, 21, 5, tzinfo=dt.UTC),
        )
    assert events == []


def test_no_frozen_lineup_quiet_for_past_slate() -> None:
    """Backfill / historical query — don't false-positive when the slate
    is yesterday and the check happens to fire today."""
    with patch.object(watchdog_checks, "get_engine", return_value=_engine_with_freeze_row(None)):
        events = watchdog._check_freeze(
            "2026-05-26",
            now_utc=dt.datetime(2026, 5, 27, 23, 0, tzinfo=dt.UTC),
        )
    assert events == []


def test_no_frozen_lineup_tip_relative_overdue_fires_before_22utc() -> None:
    """E: an afternoon slate (deadline 15:30) escalates critical at 15:45,
    hours before the legacy 22:00 UTC rule would ever look."""
    deadline = dt.datetime(2026, 6, 14, 15, 30, tzinfo=dt.UTC)
    with (
        patch.object(watchdog_checks, "get_engine", return_value=_engine_with_freeze_row(None)),
        patch.object(watchdog_checks, "_slate_freeze_deadline", return_value=deadline),
    ):
        events = watchdog._check_freeze(
            "2026-06-14",
            now_utc=dt.datetime(2026, 6, 14, 15, 45, tzinfo=dt.UTC),
        )
    assert len(events) == 1
    assert events[0].trigger == "no_frozen_lineup"
    assert events[0].severity == "critical"
    assert events[0].payload["freeze_deadline_utc"] == deadline.isoformat()


def test_no_frozen_lineup_tip_relative_quiet_before_deadline() -> None:
    """Before the tip-relative deadline, a missing freeze is not yet overdue."""
    deadline = dt.datetime(2026, 6, 14, 15, 30, tzinfo=dt.UTC)
    with (
        patch.object(watchdog_checks, "get_engine", return_value=_engine_with_freeze_row(None)),
        patch.object(watchdog_checks, "_slate_freeze_deadline", return_value=deadline),
    ):
        events = watchdog._check_freeze(
            "2026-06-14",
            now_utc=dt.datetime(2026, 6, 14, 15, 0, tzinfo=dt.UTC),
        )
    assert events == []


def test_missing_per_player_block_triggers_error() -> None:
    lineup = {"player_ids": [1, 2, 3, 4, 5], "slot_multipliers": [1.5]}  # no per_player
    row = (json.dumps(lineup), 1.2, dt.datetime.now(dt.UTC))
    with patch.object(watchdog_checks, "get_engine", return_value=_engine_with_freeze_row(row)):
        events = watchdog._check_freeze(
            "2026-05-27",
            now_utc=dt.datetime(2026, 5, 27, 22, 30, tzinfo=dt.UTC),
        )
    triggers = {e.trigger for e in events}
    assert "missing_per_player" in triggers


def test_zero_expected_payout_triggers_warn() -> None:
    lineup = {"per_player": [{"player_id": i} for i in (1, 2, 3, 4, 5)]}
    row = (json.dumps(lineup), 0.0, dt.datetime.now(dt.UTC))
    with patch.object(watchdog_checks, "get_engine", return_value=_engine_with_freeze_row(row)):
        events = watchdog._check_freeze("2026-05-27")
    triggers = {e.trigger for e in events}
    assert "zero_expected_payout" in triggers


def test_healthy_freeze_no_events() -> None:
    lineup = {"per_player": [{"player_id": i} for i in (1, 2, 3, 4, 5)]}
    row = (json.dumps(lineup), 1.4, dt.datetime.now(dt.UTC))
    with patch.object(watchdog_checks, "get_engine", return_value=_engine_with_freeze_row(row)):
        events = watchdog._check_freeze("2026-05-27")
    assert events == []


def test_run_watchdog_aggregates_and_persists() -> None:
    """run_watchdog composes _check_pool + _check_freeze + persist. Patch
    each leaf so this test stays focused on the aggregation logic and
    doesn't have to thread two different SQL result shapes through one
    mock engine."""
    pool_ev = watchdog.WatchdogEvent(
        slate_date="2026-05-27",
        trigger="no_job1_pool",
        severity=watchdog.SEVERITY_CRITICAL,
        payload={"pool_size": 0},
    )
    freeze_ev = watchdog.WatchdogEvent(
        slate_date="2026-05-27",
        trigger="no_frozen_lineup",
        severity=watchdog.SEVERITY_CRITICAL,
        payload={"note": "no row"},
    )
    with (
        patch.object(watchdog, "_check_pool", return_value=[pool_ev]),
        patch.object(watchdog, "_check_enrichment_freshness", return_value=[]),
        patch.object(watchdog, "_check_freeze", return_value=[freeze_ev]),
        patch.object(watchdog, "_check_model_artifact", return_value=[]),
        patch.object(watchdog, "_check_feature_content", return_value=[]),
        patch.object(watchdog, "_check_config_drift", return_value=[]),
        patch.object(watchdog, "_check_enrichment_source", return_value=[]),
        patch.object(watchdog, "persist_events", return_value=2) as persist,
        patch.object(watchdog, "_ping_on_critical") as ping,
    ):
        events = watchdog.run_watchdog(
            "2026-05-27",
            now_utc=dt.datetime(2026, 5, 27, 23, 0, tzinfo=dt.UTC),
        )
    triggers = {e.trigger for e in events}
    assert triggers == {"no_job1_pool", "no_frozen_lineup"}
    persist.assert_called_once_with([pool_ev, freeze_ev])
    ping.assert_called_once_with([pool_ev, freeze_ev])


def test_model_artifact_unset_is_critical() -> None:
    """Empty WNBA_ORACLE_MODEL_ARTIFACT_SHA = silent heuristic fallback."""
    events = watchdog._check_model_artifact("2026-06-21", model_sha="")
    assert [e.trigger for e in events] == ["model_artifact_unset"]
    assert events[0].severity == watchdog.SEVERITY_CRITICAL


def test_model_artifact_unresolved_is_critical(tmp_path) -> None:
    """SHA set but no matching .pkl shipped = silent heuristic fallback."""
    events = watchdog._check_model_artifact(
        "2026-06-21", model_sha="deadbeef" * 8, models_dir=tmp_path
    )
    assert [e.trigger for e in events] == ["model_artifact_unresolved"]
    assert events[0].severity == watchdog.SEVERITY_CRITICAL


def test_model_artifact_resolves_clean(tmp_path) -> None:
    from wnba_oracle.train.pipeline import PickerArtifact

    payload = pickle.dumps(PickerArtifact(feature_module_sha="test", config={}))
    sha = hashlib.sha256(payload).hexdigest()
    (tmp_path / "picker_x_1.sha256").write_text(sha)
    (tmp_path / "picker_x_1.pkl").write_bytes(payload)
    assert watchdog._check_model_artifact("2026-06-21", model_sha=sha, models_dir=tmp_path) == []


def test_model_artifact_matching_sidecar_but_corrupt_pickle_is_critical(tmp_path) -> None:
    payload = b"not a pickle"
    sha = hashlib.sha256(payload).hexdigest()
    (tmp_path / "picker_x_1.sha256").write_text(sha)
    (tmp_path / "picker_x_1.pkl").write_bytes(payload)

    events = watchdog._check_model_artifact("2026-06-21", model_sha=sha, models_dir=tmp_path)

    assert [event.trigger for event in events] == ["model_artifact_unresolved"]
    assert events[0].severity == watchdog.SEVERITY_CRITICAL


def _engine_with_feature_counts(n: int, n_odds: int, n_starter: int) -> MagicMock:
    eng = MagicMock()
    result = MagicMock()
    result.first.return_value = (n, n_odds, n_starter)
    conn = MagicMock()
    conn.execute.return_value = result
    eng.connect.return_value.__enter__.return_value = conn
    return eng


def test_feature_content_warns_on_empty_odds_and_rotowire() -> None:
    eng = _engine_with_feature_counts(20, 0, 0)
    with patch.object(watchdog_checks, "get_engine", return_value=eng):
        events = watchdog._check_feature_content("2026-06-21")
    triggers = {e.trigger for e in events}
    assert triggers == {"odds_empty", "rotowire_empty"}
    assert all(e.severity == watchdog.SEVERITY_WARN for e in events)


def test_feature_content_clean_when_feeds_present() -> None:
    eng = _engine_with_feature_counts(20, 18, 9)
    with patch.object(watchdog_checks, "get_engine", return_value=eng):
        assert watchdog._check_feature_content("2026-06-21") == []


def test_feature_content_quiet_on_tiny_pool() -> None:
    """Below 10 rows is the _check_pool checks' job; don't double-warn."""
    eng = _engine_with_feature_counts(4, 0, 0)
    with patch.object(watchdog_checks, "get_engine", return_value=eng):
        assert watchdog._check_feature_content("2026-06-21") == []


def test_settings_config_drift_detects_reverted_knob() -> None:
    """Settings.config_drift compares active knobs to EXPECTED_PROD_CONFIG.
    Duck-typed via SimpleNamespace to avoid pydantic env-loading nondeterminism."""
    import types

    from wnba_oracle.common.settings import EXPECTED_PROD_CONFIG, Settings

    prod = types.SimpleNamespace(**EXPECTED_PROD_CONFIG)
    assert Settings.config_drift(prod) == []  # type: ignore[arg-type]
    reverted = types.SimpleNamespace(**{**EXPECTED_PROD_CONFIG, "lineup_anchor_floor": 0})
    drift = Settings.config_drift(reverted)  # type: ignore[arg-type]
    assert [d[0] for d in drift] == ["lineup_anchor_floor"]


class _StubSettings:
    def __init__(self, drift):
        self._drift = drift

    def config_drift(self):
        return self._drift


def test_config_drift_warns_when_knob_reverted() -> None:
    s = _StubSettings([("optimizer_game_stack_bonus", 0.0, 0.010)])
    events = watchdog._check_config_drift("2026-06-21", settings=s)
    assert [e.trigger for e in events] == ["config_drift"]
    assert events[0].severity == watchdog.SEVERITY_WARN
    assert "optimizer_game_stack_bonus" in events[0].payload["drift"]


def test_config_drift_clean_when_env_matches_prod() -> None:
    assert watchdog._check_config_drift("2026-06-21", settings=_StubSettings([])) == []


def test_summarize_status_picks_highest_severity() -> None:
    from wnba_oracle.api.watchdog_router import _summarize  # local import keeps test deps minimal

    assert _summarize([]) == "ok"
    assert _summarize([{"severity": "warn"}]) == "warn"
    assert _summarize([{"severity": "warn"}, {"severity": "error"}]) == "error"
    assert (
        _summarize([{"severity": "warn"}, {"severity": "error"}, {"severity": "critical"}])
        == "critical"
    )


def test_pearson_basic() -> None:
    assert watchdog._pearson([(1.0, 2.0), (2.0, 4.0), (3.0, 6.0)]) == 1.0
    assert watchdog._pearson([(1.0, 6.0), (2.0, 4.0), (3.0, 2.0)]) == -1.0
    assert watchdog._pearson([]) is None
    assert watchdog._pearson([(1.0, 1.0), (1.0, 2.0)]) is None  # n<3
    assert watchdog._pearson([(1.0, 5.0), (1.0, 5.0), (1.0, 5.0)]) is None  # zero variance


def test_check_prediction_drift_fires_on_bad_corr(monkeypatch) -> None:
    """Corr under DRIFT_CORR_WARN triggers a WARN, given enough pick pairs."""

    def _stub(window: int = watchdog.DRIFT_WINDOW) -> dict[str, object]:
        assert window == watchdog.DRIFT_WINDOW
        return {
            "n_slates": 20,
            "n_pick_pairs": watchdog.DRIFT_MIN_PICK_PAIRS,
            "pick_pred_vs_real_corr": 0.10,
            "median_score_gap": -18.0,
            "worst_score_gap": -30.0,
            "best_score_gap": -5.0,
        }

    monkeypatch.setattr(watchdog_drift, "compute_drift_metrics", _stub)
    events = watchdog._check_prediction_drift("2026-07-03")
    triggers = [e.trigger for e in events]
    assert "prediction_calibration_drift" in triggers
    assert "lineup_gap_regression" not in triggers  # gap above threshold


def test_check_prediction_drift_silent_when_underpowered(monkeypatch) -> None:
    """A bad corr on too few pick pairs must NOT fire (2026-08-03).

    The alert ran for a month on 15-20 pairs, where the 95% CI spans both the
    healthy pooled history and the D77 baseline it is compared against. Below
    DRIFT_MIN_PICK_PAIRS the reading cannot separate the two, so it is noise
    rather than a retrain signal.
    """

    def _stub(window: int = watchdog.DRIFT_WINDOW) -> dict[str, object]:
        assert window == watchdog.DRIFT_WINDOW
        return {
            "n_slates": 4,
            "n_pick_pairs": watchdog.DRIFT_MIN_PICK_PAIRS - 1,
            "pick_pred_vs_real_corr": 0.285,
            "median_score_gap": -18.0,
            "worst_score_gap": -30.0,
            "best_score_gap": -5.0,
        }

    monkeypatch.setattr(watchdog_drift, "compute_drift_metrics", _stub)
    assert watchdog._check_prediction_drift("2026-07-03") == []


def test_check_prediction_drift_fires_on_bad_gap(monkeypatch) -> None:
    def _stub(window: int = watchdog.DRIFT_WINDOW) -> dict[str, object]:
        assert window == watchdog.DRIFT_WINDOW
        return {
            "n_slates": 10,
            "n_pick_pairs": 50,
            "pick_pred_vs_real_corr": 0.55,  # healthy
            "median_score_gap": -30.0,  # regressed
            "worst_score_gap": -40.0,
            "best_score_gap": -12.0,
        }

    monkeypatch.setattr(watchdog_drift, "compute_drift_metrics", _stub)
    events = watchdog._check_prediction_drift("2026-07-03")
    triggers = [e.trigger for e in events]
    assert "lineup_gap_regression" in triggers
    assert "prediction_calibration_drift" not in triggers


def test_check_prediction_drift_silent_at_baseline(monkeypatch) -> None:
    """At the loss-ledger baseline (~-17, ~0.554), the check must NOT fire.
    Steady-state under baseline is knowingly poor -- alerting on it is spam."""

    def _stub(window: int = watchdog.DRIFT_WINDOW) -> dict[str, object]:
        assert window == watchdog.DRIFT_WINDOW
        return {
            "n_slates": 10,
            "n_pick_pairs": 50,
            "pick_pred_vs_real_corr": 0.554,
            "median_score_gap": -17.0,
            "worst_score_gap": -25.0,
            "best_score_gap": -7.0,
        }

    monkeypatch.setattr(watchdog_drift, "compute_drift_metrics", _stub)
    assert watchdog._check_prediction_drift("2026-07-03") == []


def test_check_prediction_drift_silent_when_no_data(monkeypatch) -> None:
    monkeypatch.setattr(watchdog_drift, "compute_drift_metrics", lambda **_: None)
    assert watchdog._check_prediction_drift("2026-07-03") == []


def test_route_order_today_before_slate_param() -> None:
    """FastAPI matches routes in declaration order. If /{slate_date} is
    declared before /today, requests to /watchdog/today silently bind
    slate_date='today' and return empty events. Pin the order."""
    from wnba_oracle.api.watchdog_router import router

    watchdog_paths = [r.path for r in router.routes if hasattr(r, "path")]
    today_idx = watchdog_paths.index("/watchdog/today")
    param_idx = watchdog_paths.index("/watchdog/{slate_date}")
    assert today_idx < param_idx, (
        "/watchdog/today must be declared before /watchdog/{slate_date} or it "
        "will be shadowed at runtime."
    )
