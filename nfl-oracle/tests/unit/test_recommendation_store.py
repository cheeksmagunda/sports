from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError

import nfl_oracle.recommendations.app as recommendation_app
from nfl_oracle.recommendations.app import create_app
from nfl_oracle.recommendations.schema import fingerprint
from nfl_oracle.recommendations.store import RecommendationStore, migrate
from tests.unit.test_recommendation_contracts import NOW, sample_slate


def setup_store(tmp_path: Path) -> RecommendationStore:
    engine = create_engine(f"sqlite:///{tmp_path / 'decisions.db'}")
    migrate(engine)
    return RecommendationStore(engine, writable=True, clock=lambda: NOW)


def save(store: RecommendationStore, *, model: str = "model-v1") -> dict:
    return store.freeze(
        sample_slate(),
        {"picks": [{"player_id": i} for i in range(1, 6)]},
        model_fingerprint=model,
        input_fingerprint="inputs-v1",
        decision_at=NOW,
    )


def test_history_restart_duplicate_and_readonly(tmp_path: Path) -> None:
    writer = setup_store(tmp_path)
    first = save(writer)
    assert save(writer) == first
    second = save(writer, model="model-v2")
    assert second["sequence"] == 2
    assert second["previous_digest"] == first["digest"]
    reader = RecommendationStore(writer.engine)
    assert reader.latest(NOW.date()) == second
    assert len(reader.export_records()["records"]) == 2
    with pytest.raises(PermissionError):
        save(reader)
    with pytest.raises(DatabaseError, match="append_only"):
        with writer.engine.begin() as conn:
            conn.execute(text("DELETE FROM nfl_recommendation_freezes"))


def test_concurrent_freezes_are_serial_and_idempotent(tmp_path: Path) -> None:
    store = setup_store(tmp_path)
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: save(store), range(10)))
    assert {r["sequence"] for r in results} == {1}
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda i: save(store, model=f"new-{i}"), range(5)))
    assert len(store.export_records()["records"]) == 6


def test_late_write_and_future_decision_denied(tmp_path: Path) -> None:
    store = setup_store(tmp_path)
    first = save(store)
    store.clock = lambda: sample_slate().cutoff()
    # Retry returns the previously durable fact without creating a postlock row.
    assert save(store) == first
    with pytest.raises(ValueError, match="slate_locked"):
        save(store, model="changed")
    store.clock = lambda: NOW - timedelta(seconds=1)
    with pytest.raises(ValueError, match="future_decision"):
        save(store, model="future")
    assert len(store.history()) == 1


def test_freeze_rejects_malformed_or_entry_enabled_lineups(tmp_path: Path) -> None:
    store = setup_store(tmp_path)
    with pytest.raises(ValueError, match="invalid_pick"):
        store.freeze(
            sample_slate(),
            {"picks": [1, 2, 3, 4, 5]},
            model_fingerprint="model",
            input_fingerprint="inputs",
            decision_at=NOW,
        )
    with pytest.raises(ValueError, match="contest_entry_forbidden"):
        store.freeze(
            sample_slate(),
            {"picks": [{"player_id": i} for i in range(1, 6)], "contest_entry": True},
            model_fingerprint="model",
            input_fingerprint="inputs",
            decision_at=NOW,
        )


def test_changed_cutoff_cannot_reopen_locked_history(tmp_path: Path) -> None:
    store = setup_store(tmp_path)
    save(store)
    store.clock = lambda: sample_slate().cutoff()
    slate = sample_slate()
    later = slate.model_copy(
        update={
            "games": tuple(
                g.model_copy(update={"kickoff_at": g.kickoff_at + timedelta(days=1)})
                for g in slate.games
            )
        }
    )
    with pytest.raises(ValueError, match="slate_locked"):
        store.freeze(
            later,
            {"picks": [{"player_id": i} for i in range(1, 6)]},
            model_fingerprint="new",
            input_fingerprint="new",
            decision_at=NOW,
        )


def test_export_restore_round_trip_and_tamper_rejection(tmp_path: Path) -> None:
    source = setup_store(tmp_path)
    first = save(source)
    save(source, model="model-v2")
    backup = source.export_records()

    restored_engine = create_engine(f"sqlite:///{tmp_path / 'restored.db'}")
    migrate(restored_engine)
    restored = RecommendationStore(restored_engine, writable=True, clock=lambda: NOW)
    restored.restore_records(backup)
    assert restored.export_records() == backup
    assert restored.latest(NOW.date())["digest"] == backup["records"][-1]["digest"]

    tampered = dict(backup)
    tampered["records"] = [dict(first, digest="0" * 64)]
    tampered["digest"] = fingerprint(tampered["records"])
    with pytest.raises(ValueError, match="frozen_record_integrity_failure"):
        RecommendationStore(
            create_engine(f"sqlite:///{tmp_path / 'bad.db'}"), writable=True
        ).restore_records(tampered)


def test_artifacts_are_content_addressed_and_restart_durable(tmp_path: Path) -> None:
    writer = setup_store(tmp_path)
    payload = {"schema_version": 1, "rows": [{"player_id": 12, "value": 4.5}]}
    sha = writer.put_artifact("model", payload)
    assert writer.put_artifact("model", payload) == sha
    assert writer.get_artifact(sha) == {
        "sha256": sha,
        "kind": "model",
        "payload": payload,
        "created_at": NOW.isoformat(),
    }
    assert writer.latest_artifact("model")["sha256"] == sha
    writer.record_run(
        NOW.date(),
        status="waiting",
        detail_code="before_t_minus_40",
        details={"next_freeze": {"at": (NOW + timedelta(minutes=5)).isoformat()}},
    )
    backup = writer.export_backup()
    restored_engine = create_engine(f"sqlite:///{tmp_path / 'backup.db'}")
    migrate(restored_engine)
    restored = RecommendationStore(restored_engine, writable=True, clock=lambda: NOW)
    restored.restore_backup(backup)
    assert restored.export_backup() == backup
    reader = RecommendationStore(writer.engine)
    assert reader.get_artifact(sha)["payload"] == payload
    with pytest.raises(PermissionError):
        reader.put_artifact("model", payload)
    with pytest.raises(ValueError, match="unsafe_artifact_kind"):
        writer.put_artifact("model/unsafe", payload)
    with pytest.raises(DatabaseError, match="append_only"):
        with writer.engine.begin() as conn:
            conn.execute(text("DELETE FROM nfl_recommendation_artifacts"))


def test_concurrent_artifact_puts_are_idempotent(tmp_path: Path) -> None:
    store = setup_store(tmp_path)
    payload = {"rows": [1, 2, 3]}
    with ThreadPoolExecutor(max_workers=5) as pool:
        hashes = list(pool.map(lambda _: store.put_artifact("context", payload), range(10)))
    assert len(set(hashes)) == 1
    assert store.get_artifact(hashes[0])["payload"] == payload


def test_api_only_reads_and_validates_dates(tmp_path: Path) -> None:
    writer = setup_store(tmp_path)
    reader = RecommendationStore(writer.engine)
    client = TestClient(
        create_app(reader, clock=lambda: NOW, frontend_dir=Path(__file__).parents[2] / "frontend")
    )
    assert client.get("/health").status_code == 200
    assert client.get("/lineup/2026-09-09").json()["status"] == "waiting"
    writer.record_run(NOW.date(), status="no_slate", detail_code="no_contest")
    assert client.get("/lineup/2026-09-09").json()["status"] == "no_slate"
    save(writer)
    response = client.get("/lineup/2026-09-09")
    assert response.json()["status"] == "frozen"
    assert len(response.json()["lineup"]["picks"]) == 5
    assert response.json()["lineup"]["contest_entry"] is False
    assert response.json()["contest_entry"] is False
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/lineup/invalid").status_code == 422
    assert client.post("/lineup/2026-09-09").status_code == 405
    assert "lineup" not in client.get("/slate/2026-09-09").json()
    assert "slate" not in client.get("/history").json()["records"][0]
    assert client.get("/").status_code == 200
    assert client.get("/app.js").status_code == 200
    assert client.get("/../store.py").status_code == 404
    locked = TestClient(create_app(reader, clock=lambda: sample_slate().cutoff()))
    assert locked.get("/lineup/2026-09-09").json()["status"] == "locked"


def test_api_frontend_is_safe_and_exposes_empty_error_states(tmp_path: Path) -> None:
    writer = setup_store(tmp_path)
    reader = RecommendationStore(writer.engine)
    frontend = Path(__file__).parents[2] / "frontend"
    client = TestClient(create_app(reader, frontend_dir=frontend, clock=lambda: NOW))

    page = client.get("/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert 'id="picks"' in page.text
    assert 'aria-live="polite"' in page.text
    script = client.get("/app.js")
    assert script.status_code == 200
    assert "innerHTML" not in script.text
    assert "createElement" in script.text
    for state in ("No slate today", "Picks are not ready", "Picks are unavailable"):
        assert state in script.text
    # Player identity rendered without numeric projections (removed by design)
    assert "pick.name" in script.text
    assert "pick.position" in script.text
    assert "Entries are never submitted automatically" in page.text
    assert "Player 1" not in page.text + script.text
    assert client.get("/style.css").status_code == 200

    writer.record_run(NOW.date(), status="error", detail_code="provider_timeout")
    assert client.get("/lineup/2026-09-09").json()["status"] == "error"
    writer.record_run(NOW.date(), status="blocked", detail_code="missing_context")
    assert client.get("/lineup/2026-09-09").json()["status"] == "blocked"
    writer.record_run(
        NOW.date(),
        status="waiting",
        detail_code="before_t_minus_40",
        details={"next_freeze": {"at": (NOW + timedelta(minutes=5)).isoformat()}},
    )
    waiting = client.get("/lineup/2026-09-09").json()
    assert waiting["status"] == "waiting"
    assert waiting["next_freeze"]["at"] == (NOW + timedelta(minutes=5)).isoformat()


def test_env_app_uses_postgres_read_only_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NFL_DATABASE_URL", "postgresql://example.invalid/nfl")
    observed: dict[str, object] = {}
    engine = create_engine("sqlite://")

    def fake_engine(url: str, **options: object):
        observed["url"] = url
        observed.update(options)
        return engine

    monkeypatch.setattr(recommendation_app, "create_postgres_engine", fake_engine)
    recommendation_app.app_from_env()
    assert observed["url"] == "postgresql://example.invalid/nfl"
    assert observed["connect_args"] == {
        "connect_timeout": 5,
        "options": "-c default_transaction_read_only=on -c statement_timeout=5000",
    }


def test_unmigrated_database_is_unhealthy_without_mutation(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    client = TestClient(create_app(RecommendationStore(engine)))
    assert client.get("/health").status_code == 503
    assert client.get("/lineup/2026-09-09").status_code == 503
    with engine.connect() as conn:
        assert (
            conn.execute(text("SELECT count(*) FROM sqlite_master WHERE type='table'")).scalar()
            == 0
        )
