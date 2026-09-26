"""GitHub Issues are work items with a solution, never job status (issue #442).

No workflow, composite action, or repository script may create, comment on,
label, reopen, or close an issue to report job, probe, watchdog, punch-list,
or context-freshness status. A job's signal is its own Actions run plus that
run's job summary. The Claude Code workflow is the one allowed holder of
``issues: write``: it answers ``@claude`` comments and files no status issues.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ISSUE_COMMENT_RESPONDER = ROOT / ".github" / "workflows" / "claude.yml"

GH_ISSUE_OR_LABEL = re.compile(r"\bgh\s+(?:issue|label)\b")
REST_ISSUES_WRITE = re.compile(r"\bgh\s+api\b[^\n]*/issues\b")
ISSUES_WRITE_PERMISSION = re.compile(r"^\s*issues\s*:\s*write\b", re.MULTILINE)
ISSUE_FILING_ACTIONS = re.compile(
    r"uses:\s*[^\s#]*(?:create-issue|create-an-issue|issue-creator|actions/github-script)",
    re.IGNORECASE,
)


def _actions_files() -> list[Path]:
    github = ROOT / ".github"
    files = sorted((github / "workflows").glob("*.yml"))
    files += sorted((github / "workflows").glob("*.yaml"))
    files += sorted((github / "actions").glob("*/action.yml"))
    files += sorted((github / "actions").glob("*/action.yaml"))
    return files


def _script_files() -> list[Path]:
    candidates = [path for path in (ROOT / "scripts").iterdir() if path.is_file()]
    for app in ("wnba-oracle", "nfl-oracle", "nba-oracle", "nhl-oracle"):
        scripts = ROOT / app / "scripts"
        if scripts.is_dir():
            candidates += [path for path in scripts.rglob("*") if path.is_file()]
    return sorted(path for path in candidates if path.suffix in {"", ".py", ".sh"})


def _violations(paths: list[Path], pattern: re.Pattern[str]) -> list[str]:
    found = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            found.append(f"{path.relative_to(ROOT)}:{line}: {match.group(0).strip()}")
    return found


def test_actions_files_are_discovered() -> None:
    names = {path.name for path in _actions_files()}
    assert "watchdog-monitor.yml" in names
    assert "action.yml" in names


def test_no_workflow_or_action_runs_gh_issue_or_label() -> None:
    assert _violations(_actions_files(), GH_ISSUE_OR_LABEL) == []
    assert _violations(_actions_files(), REST_ISSUES_WRITE) == []


def test_no_workflow_uses_an_issue_filing_action() -> None:
    assert _violations(_actions_files(), ISSUE_FILING_ACTIONS) == []


def test_only_the_comment_responder_holds_issues_write() -> None:
    holders = [
        path
        for path in _actions_files()
        if ISSUES_WRITE_PERMISSION.search(path.read_text())
    ]
    assert holders == [ISSUE_COMMENT_RESPONDER]


def test_no_repository_script_files_issues() -> None:
    assert _violations(_script_files(), GH_ISSUE_OR_LABEL) == []
    assert _violations(_script_files(), REST_ISSUES_WRITE) == []
