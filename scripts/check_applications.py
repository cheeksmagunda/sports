#!/usr/bin/env python3
"""Validate the minimum contract for every top-level sport application."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
import re

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "AGENTS.md",
    "README.md",
    "STATUS.md",
    ".env.example",
    "Makefile",
    "pyproject.toml",
)
REQUIRED_DIRECTORIES = ("src", "tests")
REQUIRED_TARGETS = ("test", "lint", "typecheck")


def _python_packages(source: Path) -> list[Path]:
    return sorted(
        path
        for path in source.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    )


def validate_application(project: Path) -> list[str]:
    """Return actionable contract errors for one ``*-oracle`` directory."""
    errors: list[str] = []
    for name in REQUIRED_FILES:
        if not (project / name).is_file():
            errors.append(f"{project.name}: missing {name}")
    for name in REQUIRED_DIRECTORIES:
        if not (project / name).is_dir():
            errors.append(f"{project.name}: missing {name}/")

    source = project / "src"
    if source.is_dir():
        packages = _python_packages(source)
        if len(packages) != 1:
            errors.append(
                f"{project.name}: src/ must contain exactly one Python package"
            )

    pyproject = project / "pyproject.toml"
    if pyproject.is_file():
        try:
            document = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"{project.name}: invalid pyproject.toml ({exc})")
        else:
            metadata = document.get("project")
            if not isinstance(metadata, dict):
                errors.append(f"{project.name}: pyproject.toml has no [project] table")
            else:
                if metadata.get("name") != project.name:
                    errors.append(
                        f"{project.name}: [project].name must equal the application directory"
                    )
                dependencies = metadata.get("dependencies", [])
                if not any(
                    isinstance(dep, str)
                    and dep.split("[", 1)[0].split("=", 1)[0].strip() == "oracle-core"
                    for dep in dependencies
                ):
                    errors.append(
                        f"{project.name}: pyproject.toml must depend on oracle-core"
                    )

    makefile = project / "Makefile"
    if makefile.is_file():
        contents = makefile.read_text(encoding="utf-8")
        for target in REQUIRED_TARGETS:
            if re.search(rf"(?m)^{re.escape(target)}:", contents) is None:
                errors.append(f"{project.name}: Makefile missing {target} target")
    return errors


def main() -> int:
    projects = sorted(path for path in WORKSPACE_ROOT.glob("*-oracle") if path.is_dir())
    if not projects:
        print("Application contract: no sport applications found", file=sys.stderr)
        return 1

    errors = [error for project in projects for error in validate_application(project)]
    if errors:
        print("Application contract violations:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    print(f"Application contract: ok ({len(projects)} application(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
