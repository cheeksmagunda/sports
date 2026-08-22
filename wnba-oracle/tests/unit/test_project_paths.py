from pathlib import Path

from wnba_oracle.common.paths import resolve_project_root


def test_resolve_project_root_from_noneditable_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "sports"
    project = workspace / "wnba-oracle"
    (project / "src" / "wnba_oracle").mkdir(parents=True)
    installed_module = tmp_path / "venv" / "site-packages" / "wnba_oracle" / "module.py"

    monkeypatch.chdir(workspace)

    assert resolve_project_root(installed_module) == project
