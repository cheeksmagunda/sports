from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_applications import validate_application


def _write_valid_application(project: Path) -> None:
    project.mkdir()
    for name in ("AGENTS.md", "README.md", "STATUS.md", ".env.example"):
        (project / name).write_text("", encoding="utf-8")
    (project / "Makefile").write_text("test:\nlint:\ntypecheck:\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        '[project]\nname = "mlb-oracle"\ndependencies = ["oracle-core==0.1.0"]\n',
        encoding="utf-8",
    )
    (project / "src" / "mlb_oracle").mkdir(parents=True)
    (project / "src" / "mlb_oracle" / "__init__.py").write_text("", encoding="utf-8")
    (project / "tests").mkdir()


def test_valid_application_contract(tmp_path: Path) -> None:
    project = tmp_path / "mlb-oracle"
    _write_valid_application(project)

    assert validate_application(project) == []


def test_application_contract_reports_missing_core_dependency(tmp_path: Path) -> None:
    project = tmp_path / "mlb-oracle"
    _write_valid_application(project)
    (project / "pyproject.toml").write_text(
        '[project]\nname = "mlb-oracle"\ndependencies = []\n',
        encoding="utf-8",
    )

    assert validate_application(project) == [
        "mlb-oracle: pyproject.toml must depend on oracle-core"
    ]
