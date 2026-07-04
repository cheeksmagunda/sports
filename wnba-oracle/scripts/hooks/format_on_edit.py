#!/usr/bin/env python3
"""PostToolUse hook: ruff-format any Python file Claude edits.

Reads the hook payload from stdin, formats the touched file if it is a
.py under src/ or tests/ (the same scope as `make fmt`), and always
exits 0 so a formatter hiccup never blocks the session.
"""

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    raw = (payload.get("tool_input") or {}).get("file_path", "")
    if not raw:
        return 0

    path = pathlib.Path(raw)
    if path.suffix != ".py" or not path.is_file():
        return 0

    try:
        rel = path.resolve().relative_to(REPO)
    except ValueError:
        return 0
    if rel.parts[0] not in ("src", "tests"):
        return 0

    subprocess.run(
        ["uv", "run", "ruff", "format", "--quiet", str(path)],
        cwd=REPO,
        capture_output=True,
        timeout=60,
        check=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
