"""Regression tests for static infrastructure and model import boundaries."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


def _load_boundary_checker() -> ModuleType:
    path = WORKSPACE_ROOT / "scripts" / "check_import_boundaries.py"
    spec = importlib.util.spec_from_file_location("sports_check_import_boundaries", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load import boundary checker")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_model_kernel_cannot_import_observational_assurance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _load_boundary_checker()
    model_dir = tmp_path / "modeling"
    model_dir.mkdir()
    (model_dir / "coupled.py").write_text(
        "from wnba_oracle.assurance import build_source_assurance\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(checker, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(checker, "CORE_SOURCE", tmp_path / "oracle-core")
    monkeypatch.setattr(checker, "MODEL_KERNEL_DIRS", (model_dir,))
    monkeypatch.setattr(checker, "ASSURANCE_DIR", tmp_path / "assurance")
    monkeypatch.setattr(checker, "_applications", lambda: ())

    assert checker._violations() == [
        "modeling/coupled.py:1: model kernel cannot import operational module "
        "'wnba_oracle.assurance'"
    ]


def test_assurance_cannot_import_model_or_runtime_modules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _load_boundary_checker()
    assurance_dir = tmp_path / "assurance"
    assurance_dir.mkdir()
    (assurance_dir / "coupled.py").write_text(
        "from wnba_oracle.features import serving_schema\nfrom wnba_oracle.scheduler import job2\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(checker, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(checker, "CORE_SOURCE", tmp_path / "oracle-core")
    monkeypatch.setattr(checker, "MODEL_KERNEL_DIRS", ())
    monkeypatch.setattr(checker, "ASSURANCE_DIR", assurance_dir)
    monkeypatch.setattr(checker, "_applications", lambda: ())

    assert checker._violations() == [
        "assurance/coupled.py:1: assurance boundary cannot import runtime or model module "
        "'wnba_oracle.features'",
        "assurance/coupled.py:2: assurance boundary cannot import runtime or model module "
        "'wnba_oracle.scheduler'",
    ]


def test_relative_imports_cannot_bypass_assurance_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _load_boundary_checker()
    package_dir = tmp_path / "wnba_oracle"
    assurance_dir = package_dir / "assurance"
    model_dir = package_dir / "modeling"
    assurance_dir.mkdir(parents=True)
    model_dir.mkdir()
    for init_path in (
        package_dir / "__init__.py",
        assurance_dir / "__init__.py",
        model_dir / "__init__.py",
    ):
        init_path.write_text("", encoding="utf-8")
    (assurance_dir / "coupled.py").write_text(
        "from ..modeling import policy\n",
        encoding="utf-8",
    )
    (model_dir / "coupled.py").write_text(
        "from ..assurance import build_source_assurance\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(checker, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(checker, "CORE_SOURCE", tmp_path / "oracle-core")
    monkeypatch.setattr(checker, "MODEL_KERNEL_DIRS", (model_dir,))
    monkeypatch.setattr(checker, "ASSURANCE_DIR", assurance_dir)
    monkeypatch.setattr(checker, "_applications", lambda: ())

    assert checker._violations() == [
        "wnba_oracle/modeling/coupled.py:1: model kernel cannot import operational module "
        "'wnba_oracle.assurance'",
        "wnba_oracle/assurance/coupled.py:1: assurance boundary cannot import runtime or model "
        "module 'wnba_oracle.modeling'",
    ]
