import asyncio
import json
from datetime import date
from unittest.mock import AsyncMock, Mock

import pytest

from nfl_oracle.recommendations import cli
from nfl_oracle.recommendations.provider import NoSlate


@pytest.mark.parametrize("poll_error", [RuntimeError("poll failed"), NoSlate("no games")])
def test_worker_recovers_when_failure_audit_database_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    poll_error: Exception,
) -> None:
    monkeypatch.setenv("NFL_RECOMMENDATIONS_ENABLED", "1")
    store = Mock()
    store.record_run.side_effect = RuntimeError("password=must-not-appear")
    monkeypatch.setattr(cli, "_engine", Mock())
    monkeypatch.setattr(cli, "RecommendationStore", Mock(return_value=store))
    monkeypatch.setattr(cli, "RecommendationPipeline", Mock())
    poll = AsyncMock(side_effect=[poll_error, {"slate_date": "2026-09-09"}])
    monkeypatch.setattr(cli, "_worker_once", poll)
    sleep = AsyncMock(side_effect=[None, asyncio.CancelledError()])
    monkeypatch.setattr(cli.asyncio, "sleep", sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(cli._run_worker(False, 30, date(2026, 9, 9)))

    output = capsys.readouterr().out
    records = [json.loads(line) for line in output.splitlines()]
    assert poll.await_count == 2
    assert sleep.await_count == 2
    assert records[0]["detail_code"] == "worker_run_record_failed"
    assert records[-1] == {"status": "ready", "slate_date": "2026-09-09", "picks": 5}
    assert "password" not in output
    assert "must-not-appear" not in output


def test_worker_once_still_fails_when_poll_and_failure_audit_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NFL_RECOMMENDATIONS_ENABLED", "1")
    store = Mock()
    store.record_run.side_effect = RuntimeError("database unavailable")
    monkeypatch.setattr(cli, "_engine", Mock())
    monkeypatch.setattr(cli, "RecommendationStore", Mock(return_value=store))
    monkeypatch.setattr(cli, "RecommendationPipeline", Mock())
    monkeypatch.setattr(cli, "_worker_once", AsyncMock(side_effect=RuntimeError("poll failed")))
    sleep = AsyncMock()
    monkeypatch.setattr(cli.asyncio, "sleep", sleep)

    assert asyncio.run(cli._run_worker(True, 30, date(2026, 9, 9))) == 1
    sleep.assert_not_awaited()
