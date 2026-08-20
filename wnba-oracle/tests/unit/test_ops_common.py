"""Secret-safety tests for the portable production automation helpers."""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import sys
import urllib.error
from types import ModuleType

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts"


def _load_ops_common() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ops_common", SCRIPTS_DIR / "ops_common.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_graphql_http_error_does_not_expose_token_or_body(monkeypatch, tmp_path) -> None:
    ops = _load_ops_common()
    token = "railway-secret-token"
    response_body = b'{"errors":[{"message":"body-secret-value"}]}'

    def fail_request(*args, **kwargs):
        del args, kwargs
        raise urllib.error.HTTPError(
            ops.RAILWAY_GRAPHQL_URL,
            403,
            "Forbidden",
            {},
            io.BytesIO(response_body),
        )

    monkeypatch.setattr(ops.urllib.request, "urlopen", fail_request)
    client = ops.RailwayClient(token)
    with pytest.raises(ops.SafeRequestError) as raised:
        client.execute("query { projects { edges { node { id } } } }", {})

    error = str(raised.value)
    report = tmp_path / "report.md"
    ops.write_report(report, "Safe report", [ops.Check("Railway", "alert", error)])
    rendered = report.read_text()
    assert token not in error
    assert token not in rendered
    assert "body-secret-value" not in error
    assert "body-secret-value" not in rendered


def test_graphql_errors_do_not_expose_response_body(monkeypatch, tmp_path) -> None:
    ops = _load_ops_common()
    response_body = b'{"errors":[{"message":"database-password-in-body"}]}'

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            del args

        def read(self) -> bytes:
            return response_body

    def successful_request(*args, **kwargs) -> Response:
        del args, kwargs
        return Response()

    monkeypatch.setattr(ops.urllib.request, "urlopen", successful_request)
    with pytest.raises(ops.SafeRequestError) as raised:
        ops.RailwayClient("not-rendered").execute("query { projects { edges { node { id } } } }", {})

    report = tmp_path / "report.md"
    ops.write_report(report, "Safe report", [ops.Check("Railway", "alert", str(raised.value))])
    assert "database-password-in-body" not in report.read_text()


def _window(ops):
    return ops.RunWindow.from_strings(
        role="job1",
        slate_date="2026-08-20",
        started_at="2026-08-20T12:00:00Z",
        ended_at="2026-08-20T13:00:00Z",
    )


def test_missing_and_unknown_deployments_fail_closed() -> None:
    ops = _load_ops_common()

    assert ops.deployment_status_check("job", []).status == "alert"
    assert ops.deployment_status_check("job", [{"status": None}]).status == "alert"
    assert ops.deployment_status_check("job", [{"status": "SUCCESS"}]).status == "ok"


def test_run_evidence_rejects_stale_logs_and_accepts_exact_role_and_slate() -> None:
    ops = _load_ops_common()
    window = _window(ops)
    stale_logs = [
        {
            "timestamp": "2026-08-19T12:30:00Z",
            "message": json.dumps({"event": "cron_dispatch", "job": "job1", "role": "job1"}),
        },
        {
            "timestamp": "2026-08-19T12:31:00Z",
            "message": json.dumps({"event": "job1_done", "slate_date": "2026-08-20"}),
        },
    ]
    stale_checks = ops.run_evidence_checks(
        deployment_name="Job 1 deployment",
        completion_name="Job 1 run",
        completion_event="job1_done",
        deployments=[{"status": "SUCCESS"}],
        logs=stale_logs,
        window=window,
    )
    assert [check.status for check in stale_checks] == ["ok", "alert", "alert"]

    current_logs = [
        {
            "timestamp": "2026-08-20T12:30:00Z",
            "message": json.dumps({"event": "cron_dispatch", "job": "job1", "role": "job1"}),
        },
        {
            "timestamp": "2026-08-20T12:31:00Z",
            "message": json.dumps({"event": "job1_done", "slate_date": "2026-08-20"}),
        },
    ]
    current_checks = ops.run_evidence_checks(
        deployment_name="Job 1 deployment",
        completion_name="Job 1 run",
        completion_event="job1_done",
        deployments=[{"status": "SUCCESS"}],
        logs=current_logs,
        window=window,
    )
    assert [check.status for check in current_checks] == ["ok", "ok", "ok"]


def test_railway_evidence_is_timestamp_bounded_and_sorts_unordered_deployments(monkeypatch) -> None:
    ops = _load_ops_common()
    window = _window(ops)
    client = ops.RailwayClient("not-rendered")

    def deployments(*args, **kwargs):
        del args
        assert kwargs["limit"] == ops.MAX_DEPLOYMENT_LIMIT
        return [
            {"id": "old", "status": "SUCCESS", "createdAt": "2026-08-20T12:15:00Z"},
            {"id": "current", "status": "SUCCESS", "createdAt": "2026-08-20T12:45:00Z"},
        ]

    def logs(deployment_id, *, limit):
        assert deployment_id == "current"
        assert limit == ops.MAX_LOG_LIMIT
        return [
            {"timestamp": "2026-08-20T12:45:00Z", "message": "current"},
            {"timestamp": "2026-08-20T13:01:00Z", "message": "outside"},
        ]

    monkeypatch.setattr(client, "deployments", deployments)
    monkeypatch.setattr(client, "deployment_logs", logs)
    selected, observed = client.evidence_for_window("project", "service", window)

    assert selected == [{"id": "current", "status": "SUCCESS", "createdAt": "2026-08-20T12:45:00Z"}]
    assert observed == [{"timestamp": "2026-08-20T12:45:00Z", "message": "current"}]


def test_repair_has_bounded_attempts_cooldown_and_postcheck() -> None:
    ops = _load_ops_common()
    sleeps: list[float] = []
    postchecks = iter([False, True])
    requested: list[str] = []

    result = ops.perform_repair(
        lambda: requested.append("redeploy"),
        lambda: next(postchecks),
        policy=ops.RepairPolicy(attempts=2, cooldown_seconds=5, postcheck_seconds=3),
        sleep=sleeps.append,
    )

    assert result.recovered is True
    assert result.attempts == 2
    assert requested == ["redeploy", "redeploy"]
    assert sleeps == [3, 5, 3]
