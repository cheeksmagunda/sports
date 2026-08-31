from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_dev_services


def test_missing_configuration_fails_without_connecting(monkeypatch, capsys):
    def unexpected_connection(url):
        pytest.fail("must not connect without explicit service configuration")

    monkeypatch.setattr(check_dev_services, "probe_postgres", unexpected_connection)
    assert check_dev_services.main({}) == 1
    assert "DATABASE_URL: missing" in capsys.readouterr().out


@pytest.mark.parametrize("failed_service", ["probe_postgres", "probe_redis"])
def test_driver_failure_is_value_free(monkeypatch, capsys, failed_service):
    secret = "postgresql://user:do-not-log-this@unreachable/db"

    def fail(url):
        raise RuntimeError(f"connection failed: {secret}")

    monkeypatch.setattr(check_dev_services, "probe_postgres", lambda url: None)
    monkeypatch.setattr(check_dev_services, "probe_redis", lambda url: None)
    monkeypatch.setattr(check_dev_services, failed_service, fail)
    assert check_dev_services.main({"DATABASE_URL": secret, "REDIS_URL": secret}) == 1
    output = capsys.readouterr().out
    assert "unreachable" in output
    assert secret not in output
    assert "do-not-log-this" not in output


def test_probes_use_the_configured_services(monkeypatch):
    seen = []
    monkeypatch.setattr(
        check_dev_services, "probe_postgres", lambda url: seen.append(url)
    )
    monkeypatch.setattr(check_dev_services, "probe_redis", lambda url: seen.append(url))
    assert (
        check_dev_services.main(
            {"DATABASE_URL": "postgresql://db/dev", "REDIS_URL": "redis://redis/0"}
        )
        == 0
    )
    assert seen == ["postgresql://db/dev", "redis://redis/0"]
