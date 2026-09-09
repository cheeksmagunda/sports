"""Build and smoke-test the NFL production image without secrets or a database."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, text=True, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="nfl-oracle:production-smoke")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    dockerfile = root / "nfl-oracle" / "Dockerfile.production"
    if not dockerfile.exists():
        raise SystemExit("Dockerfile.production is missing")
    try:
        run("docker", "build", "-f", str(dockerfile), "-t", args.tag, str(root))
        help_result = run("docker", "run", "--rm", args.tag, "nfl-pipeline", "--help")
    except FileNotFoundError:
        print("docker not available; production container smoke skipped")
        return 0
    print(help_result.stdout)
    required = ("serve", "worker", "migrate")
    if not all(command in help_result.stdout for command in required):
        raise SystemExit("nfl-pipeline help does not expose serve, worker, and migrate")
    print("nfl-oracle production container smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
