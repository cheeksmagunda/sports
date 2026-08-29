#!/usr/bin/env python3
"""Enforce the workspace dependency direction with static import checks."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCE = WORKSPACE_ROOT / "packages" / "oracle-core" / "src"
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
MODEL_KERNEL_NAMES = ("modeling", "picker", "predict")
ASSURANCE_NAME = "assurance"


@dataclass(frozen=True)
class Application:
    name: str
    source: Path
    package: str
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
        packages = (
            tuple(
                path.name
                for path in source.iterdir()
                if path.is_dir() and (path / "__init__.py").is_file()
            )
            if source.is_dir()
            else ()
        )
        modules = _top_level_modules(source)
        if len(packages) == 1 and modules:
            applications.append(Application(project.name, source, packages[0], modules))
    return tuple(applications)


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                imports.append((node.lineno, node.module))
                continue
            package_parts: list[str] = []
            parent = path.parent
            while (parent / "__init__.py").is_file():
                package_parts.insert(0, parent.name)
                parent = parent.parent
            ascents = max(node.level - 1, 0)
            if ascents > len(package_parts):
                continue
            base = package_parts[: len(package_parts) - ascents]
            if node.module:
                imports.append((node.lineno, ".".join([*base, node.module])))
            else:
                imports.extend(
                    (node.lineno, ".".join([*base, alias.name])) for alias in node.names
                )
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
                    f"{relative}:{line}: oracle-core cannot import sport module {module!r}"
                )

    for application in applications:
        forbidden = application_modules.difference(application.modules)
        for path in sorted(application.source.rglob("*.py")):
            for line, module in _imports(path):
                if module.split(".", 1)[0] in forbidden:
                    relative = path.relative_to(WORKSPACE_ROOT)
                    violations.append(
                        f"{relative}:{line}: {application.name} cannot import another sport "
                        f"module {module!r}"
                    )

    for application in applications:
        model_prefixes = tuple(
            f"{application.package}.{name}"
            for name in (
                "common.clock",
                "common.settings",
                "db",
                "ingest",
                "scheduler",
                "assurance",
                "api",
            )
        ) + ("oracle_core",)
        model_dirs = tuple(
            application.source / application.package / name
            for name in MODEL_KERNEL_NAMES
            if (application.source / application.package / name).is_dir()
        )
        for source in model_dirs:
            for path in sorted(source.rglob("*.py")):
                for line, module in _imports(path):
                    top_level = module.split(".", 1)[0]
                    forbidden_prefix = next(
                        (
                            prefix
                            for prefix in model_prefixes
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
                        f"{relative}:{line}: model kernel cannot import operational module {module!r}"
                    )

        assurance_dir = application.source / application.package / ASSURANCE_NAME
        if not assurance_dir.is_dir():
            continue
        assurance_prefixes = tuple(
            f"{application.package}.{name}"
            for name in (
                "api",
                "common.settings",
                "db",
                "eval",
                "features",
                "ingest",
                "modeling",
                "picker",
                "predict",
                "scheduler",
                "train",
            )
        ) + ("oracle_core",)
        for path in sorted(assurance_dir.rglob("*.py")):
            for line, module in _imports(path):
                top_level = module.split(".", 1)[0]
                forbidden_prefix = next(
                    (
                        prefix
                        for prefix in assurance_prefixes
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
                    f"{relative}:{line}: assurance boundary cannot import runtime or model module "
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
