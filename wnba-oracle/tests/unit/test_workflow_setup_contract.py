"""Keep independent hosted jobs on the same portable Python contract."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[3] / ".github" / "workflows"
SETUP_ACTION = "./.github/actions/setup-python-uv"


def test_each_uv_job_initializes_its_own_toolchain() -> None:
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text())
        for job_name, job in workflow["jobs"].items():
            initialized = False
            for step in job.get("steps", []):
                if step.get("uses") == SETUP_ACTION:
                    initialized = True
                command = step.get("run", "")
                if re.search(r"\buv\s+(?:run|sync|lock|export)\b", command):
                    assert initialized, f"{path.name}:{job_name} uses uv before setup"


def test_backup_publisher_limits_authentication_to_the_write_step() -> None:
    workflow = yaml.safe_load((WORKFLOWS / "corpus-backup.yml").read_text())
    publisher = workflow["jobs"]["publish"]
    steps = publisher["steps"]
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout.get("with", {}).get("persist-credentials") is False
    writer = next(step for step in steps if step.get("name") == "Commit snapshot to backups branch")
    assert writer["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert "gh auth setup-git" in writer["run"]
    for step in steps:
        if step is not writer:
            assert "GH_TOKEN" not in step.get("env", {})
    assert "secrets." not in str(publisher)


def test_race_corpus_publish_is_workflow_dispatch_opt_in() -> None:
    """Race parquet publish stays behind workflow_dispatch until #337 is complete."""

    workflow = yaml.safe_load((WORKFLOWS / "corpus-backup.yml").read_text())
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert "publish_race_corpus" in inputs
    assert inputs["publish_race_corpus"]["default"] is False
    export_steps = workflow["jobs"]["export"]["steps"]
    race_build = next(
        step for step in export_steps if step.get("name") == "Build race corpus (per-season parquet)"
    )
    assert "publish_race_corpus" in race_build["if"]
    assert "workflow_dispatch" in race_build["if"]
    assert "BACKUP_DATABASE_URL" in race_build["env"]["DATABASE_PUBLIC_URL"]
    assert "build_race_corpus.py" in race_build["run"]
    size_guard = next(
        step
        for step in export_steps
        if step.get("name") == "Enforce race corpus per-file size budget"
    )
    assert "+100M" in size_guard["run"]
    verify = next(
        step for step in export_steps if step.get("name") == "Verify race manifest and hashes"
    )
    assert "--verify-only" in verify["run"]
    writer = next(
        step
        for step in workflow["jobs"]["publish"]["steps"]
        if step.get("name") == "Commit snapshot to backups branch"
    )
    assert "wnba-oracle/data/race" in writer["run"]
