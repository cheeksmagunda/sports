#!/usr/bin/env python3
"""Regenerate FILES.md: a one-line-per-file manifest of every tracked file.

Never hand-edit FILES.md. Run this script instead; use --check to verify it
is already up to date (exits 1 and prints a diff-free mismatch notice if not).
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path

HEADER = "# File manifest (generated, do not hand-edit)"


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(out.stdout.strip())


def tracked_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
    )
    return sorted(out.stdout.splitlines())


def purpose(path: Path) -> str:
    try:
        if path.suffix == ".py":
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            doc = ast.get_docstring(tree)
            return doc.strip().splitlines()[0][:100] if doc else ""
        if path.suffix == ".md":
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("# "):
                    return line[2:].strip()[:100]
            return ""
        if path.name == "Makefile":
            return "Build/test/lint entrypoints"
        if path.suffix in (".yml", ".yaml") and "workflows" in str(path):
            return "GitHub Actions workflow"
        if path.suffix == ".toml":
            return "Package/tool configuration"
        if path.suffix == ".json" and "fixtures" in str(path):
            return "(test fixture data)"
        if path.suffix == ".csv":
            return "(data file)"
        if path.suffix == ".lock":
            return "Locked dependency graph"
        if path.suffix == ".sh":
            return "Shell script"
        if path.suffix == ".html":
            return "Static frontend page"
        return ""
    except (OSError, SyntaxError, UnicodeDecodeError):
        return ""


def render(root: Path, files: list[str]) -> str:
    by_dir: dict[str, list[str]] = {}
    for f in files:
        d = str(Path(f).parent)
        line = f
        pu = purpose(root / f)
        if pu:
            line += f" -- {pu}"
        by_dir.setdefault(d, []).append(line)

    note = (
        f"Generated from `git ls-files`. {len(files)} tracked files. "
        "Regenerate with `scripts/generate_file_manifest.py`."
    )
    out = [HEADER, "", note, ""]
    for d in sorted(by_dir):
        out.append(f"## {d}/" if d != "." else "## (repo root)")
        out.extend(f"- {line}" for line in by_dir[d])
        out.append("")
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if FILES.md is not up to date instead of writing it.",
    )
    args = parser.parse_args()

    root = repo_root()
    content = render(root, tracked_files(root))
    target = root / "FILES.md"

    if args.check:
        current = target.read_text(encoding="utf-8") if target.is_file() else ""
        if current != content:
            print(
                "FILES.md is out of date; run scripts/generate_file_manifest.py",
                file=sys.stderr,
            )
            raise SystemExit(1)
        print("FILES.md is up to date")
        return

    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
