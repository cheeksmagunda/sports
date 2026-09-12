from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from nfl_oracle.recommendations.store import RecommendationStore, migrate
from tests.unit.test_recommendation_contracts import NOW, sample_slate

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _import(name: str):
    sys.path.insert(0, str(SCRIPTS))
    try:
        module = importlib.import_module(name)
        return importlib.reload(module)
    finally:
        sys.path.remove(str(SCRIPTS))


def _seeded_engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'decisions.db'}")
    migrate(engine)
    store = RecommendationStore(engine, writable=True, clock=lambda: NOW)
    store.freeze(
        sample_slate(),
        {"picks": [{"player_id": i} for i in range(1, 6)]},
        model_fingerprint="model-v1",
        input_fingerprint="inputs-v1",
        decision_at=NOW,
    )
    store.put_artifact(
        f"prepared:{NOW.date().isoformat()}", {"schema_version": 1, "context": "input-snapshot"}
    )
    store.put_artifact(
        f"dayclose_grade:{NOW.date().isoformat()}",
        {
            "schema_version": 2,
            "day": NOW.date().isoformat(),
            "contest_id": 2141,
            "grade": {"status": "complete"},
            "slate_results": {
                "contest": {"entrants": 20841},
                "top_entries": [],
                "player_draft_stats": [
                    {
                        "player_id": 99,
                        "display_name": "P. NinetyNine",
                        "team_id": 5,
                        "section": "mostDrafted",
                        "value": 12.5,
                        "draft_count": 4102,
                        "card_boost": 0.0,
                        "avg_effective_multiplier": 1.6,
                        "avg_score": 20.0,
                        "highest_score": 25.0,
                    }
                ],
                "law_verified": True,
                "missing_routes": [],
            },
        },
    )
    # A reproducible artifact kind that must NOT appear in the CSV export.
    store.put_artifact("model_bundle", {"schema_version": 1, "trained_at": NOW.isoformat()})
    return engine


def test_export_corpus_writes_only_irreplaceable_tables(tmp_path: Path) -> None:
    backup_corpus = _import("backup_corpus")
    engine = _seeded_engine(tmp_path)
    out_dir = tmp_path / "backup"

    manifest = backup_corpus.export_corpus(engine, out_dir)

    assert set(manifest["tables"]) == {
        "frozen_lineups",
        "prepared_decisions",
        "dayclose_grades",
        "player_results",
    }
    assert manifest["tables"]["frozen_lineups"]["rows"] == 1
    assert manifest["tables"]["prepared_decisions"]["rows"] == 1
    assert manifest["tables"]["dayclose_grades"]["rows"] == 1
    assert manifest["tables"]["player_results"]["rows"] == 1

    frozen_csv = (out_dir / "frozen_lineups.csv").read_text(encoding="utf-8")
    assert "contest_id" in frozen_csv.splitlines()[0]
    assert "2141" in frozen_csv
    grades_csv = (out_dir / "dayclose_grades.csv").read_text(encoding="utf-8")
    assert NOW.date().isoformat() in grades_csv
    player_results_csv = (out_dir / "player_results.csv").read_text(encoding="utf-8")
    assert "99" in player_results_csv
    assert "mostDrafted" in player_results_csv
    # model_bundle is reproducible from Corpus G and must not be exported.
    for name in (
        "frozen_lineups.csv",
        "prepared_decisions.csv",
        "dayclose_grades.csv",
        "player_results.csv",
    ):
        assert "model_bundle" not in (out_dir / name).read_text(encoding="utf-8")


def test_export_then_validate_round_trip(tmp_path: Path) -> None:
    backup_corpus = _import("backup_corpus")
    engine = _seeded_engine(tmp_path)
    out_dir = tmp_path / "backup"
    backup_corpus.export_corpus(engine, out_dir)

    common = _import("nfl_corpus_backup_common")
    verified = common.validate_snapshot(out_dir)
    assert verified["schema_version"] == 1


def test_validate_snapshot_rejects_tampered_payload(tmp_path: Path) -> None:
    backup_corpus = _import("backup_corpus")
    common = _import("nfl_corpus_backup_common")
    engine = _seeded_engine(tmp_path)
    out_dir = tmp_path / "backup"
    backup_corpus.export_corpus(engine, out_dir)

    csv_path = out_dir / "frozen_lineups.csv"
    csv_path.write_text(csv_path.read_text(encoding="utf-8") + "\ntampered,row\n", encoding="utf-8")

    with pytest.raises(common.SnapshotValidationError):
        common.validate_snapshot(out_dir)


def test_regression_guard_rejects_a_shrinking_corpus(tmp_path: Path) -> None:
    common = _import("nfl_corpus_backup_common")
    previous = tmp_path / "previous-manifest.json"
    previous.write_text(
        json.dumps({"tables": {"frozen_lineups": {"rows": 5}}}),
        encoding="utf-8",
    )
    shrunk = {"tables": {"frozen_lineups": {"rows": 1}}}

    with pytest.raises(RuntimeError, match="regression"):
        common.assert_no_regression(shrunk, previous, allow_regression=False)

    common.assert_no_regression(shrunk, previous, allow_regression=True)


def test_restore_cli_validates_a_real_snapshot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup_corpus = _import("backup_corpus")
    restore_corpus = _import("restore_corpus")
    engine = _seeded_engine(tmp_path)
    out_dir = tmp_path / "backup"
    backup_corpus.export_corpus(engine, out_dir)

    argv_backup = sys.argv
    sys.argv = ["restore_corpus.py", "--snapshot-dir", str(out_dir)]
    try:
        assert restore_corpus.main() == 0
    finally:
        sys.argv = argv_backup
    out = capsys.readouterr().out
    assert "verified corpus backup" in out


def test_restore_cli_reports_failure_for_missing_snapshot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    restore_corpus = _import("restore_corpus")
    argv_backup = sys.argv
    sys.argv = ["restore_corpus.py", "--snapshot-dir", str(tmp_path / "does-not-exist")]
    try:
        assert restore_corpus.main() == 1
    finally:
        sys.argv = argv_backup
    assert "ERROR" in capsys.readouterr().err
