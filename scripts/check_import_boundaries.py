#!/usr/bin/env python3
"""Enforce the workspace dependency direction with static import checks."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCE = WORKSPACE_ROOT / "packages" / "oracle-core" / "src"
WNBA_SOURCE = WORKSPACE_ROOT / "wnba-oracle" / "src" / "wnba_oracle"
MODEL_KERNEL_DIRS = (
    WNBA_SOURCE / "modeling",
    WNBA_SOURCE / "picker",
    WNBA_SOURCE / "predict",
)
MODEL_FORBIDDEN_PREFIXES = (
    "wnba_oracle.api",
    "wnba_oracle.common.clock",
    "wnba_oracle.common.settings",
    "wnba_oracle.db",
    "wnba_oracle.ingest",
    "wnba_oracle.scheduler",
    "oracle_core",
)
MODEL_FORBIDDEN_MODULES = {
    "fastapi",
    "httpx",
    "os",
    "playwright",
    "redis",
    "requests",
    "sqlalchemy",
    "subprocess",
}


@dataclass(frozen=True)
class Application:
    name: str
    source: Path
    modules: frozenset[str]


def _top_level_modules(source: Path) -> frozenset[str]:
    if not source.is_dir():
        return frozenset()
    return frozenset(
        path.name
        for path in source.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    )


def _applications() -> tuple[Application, ...]:
    applications: list[Application] = []
    for project in sorted(WORKSPACE_ROOT.glob("*-oracle")):
        source = project / "src"
        modules = _top_level_modules(source)
        if modules:
            applications.append(Application(project.name, source, modules))
    return tuple(applications)


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.append((node.lineno, node.module))
    return imports


def _violations() -> list[str]:
    applications = _applications()
    application_modules = frozenset().union(*(app.modules for app in applications))
    violations: list[str] = []

    for path in sorted(CORE_SOURCE.rglob("*.py")):
        for line, module in _imports(path):
            if module.split(".", 1)[0] in application_modules:
                relative = path.relative_to(WORKSPACE_ROOT)
                violations.append(
                    f"{relative}:{line}: oracle-core cannot import league module {module!r}"
                )

    for application in applications:
        forbidden = application_modules.difference(application.modules)
        for path in sorted(application.source.rglob("*.py")):
            for line, module in _imports(path):
                if module.split(".", 1)[0] in forbidden:
                    relative = path.relative_to(WORKSPACE_ROOT)
                    violations.append(
                        f"{relative}:{line}: {application.name} cannot import another league "
                        f"module {module!r}"
                    )

    for source in MODEL_KERNEL_DIRS:
        for path in sorted(source.rglob("*.py")):
            for line, module in _imports(path):
                top_level = module.split(".", 1)[0]
                forbidden_prefix = next(
                    (
                        prefix
                        for prefix in MODEL_FORBIDDEN_PREFIXES
                        if module == prefix or module.startswith(f"{prefix}.")
                    ),
                    None,
                )
                if (
                    forbidden_prefix is None
                    and top_level not in MODEL_FORBIDDEN_MODULES
                ):
                    continue
                relative = path.relative_to(WORKSPACE_ROOT)
                violations.append(
                    f"{relative}:{line}: model kernel cannot import operational module "
                    f"{module!r}"
                )
    return violations


def main() -> int:
    violations = _violations()
    if violations:
        print("Import boundary violations:", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        return 1
    print("Import boundaries: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
