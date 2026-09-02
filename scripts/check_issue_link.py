#!/usr/bin/env python3
"""Enforce issue linkage for material pull request work."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

ISSUE_REF = re.compile(
    r"(?:^|[\s(])(?:#[1-9]\d*|[\w.-]+/[\w.-]+#[1-9]\d*)(?=$|[\s).,;:])"
)
PR_REF = re.compile(
    r"\b(?:closes|fixes|resolves|refs)\s+"
    r"(?:#[1-9]\d*|[\w.-]+/[\w.-]+#[1-9]\d*)\b",
    re.IGNORECASE,
)
BRANCH_ISSUE = re.compile(r"(?:^|[/-])[1-9]\d*(?:[/-]|$)")


def validation_errors(branch: str, body: str, commit_messages: list[str]) -> list[str]:
    errors: list[str] = []
    if not BRANCH_ISSUE.search(branch):
        errors.append(
            "branch name must include an issue number, for example chat/123-cleanup"
        )
    if not PR_REF.search(body):
        errors.append("PR body must include Closes/Fixes/Resolves/Refs #123")
    for index, message in enumerate(commit_messages, start=1):
        if not ISSUE_REF.search(message):
            errors.append(f"commit {index} is missing an issue reference")
    return errors


def _commit_messages(base_ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "log", "--format=%B%x00", f"{base_ref}..HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [message.strip() for message in result.stdout.split("\0") if message.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--base-ref", required=True)
    args = parser.parse_args()

    errors = validation_errors(args.branch, args.body, _commit_messages(args.base_ref))
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
