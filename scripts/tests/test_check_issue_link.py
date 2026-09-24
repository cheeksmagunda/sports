from scripts.check_issue_link import validation_errors


def test_accepts_linked_branch_pr_and_commits() -> None:
    assert (
        validation_errors(
            "chat/52-repository-cleanup",
            "Closes #52",
            ["Clean repository docs (#52)", "Add enforcement\n\nRefs #52"],
        )
        == []
    )


def test_reports_each_missing_link() -> None:
    errors = validation_errors("cleanup", "No link", ["First", "Second (#52)"])

    assert errors == [
        "branch name must include an issue number, for example chat/123-cleanup",
        "PR body must include Closes/Fixes/Resolves/Refs #123",
        "commit 1 is missing an issue reference",
    ]


def test_accepts_cross_repository_issue_reference() -> None:
    assert (
        validation_errors(
            "feature/52-cleanup",
            "Refs cheeksmagunda/sports#52",
            ["Clean docs\n\nRefs cheeksmagunda/sports#52"],
        )
        == []
    )


def test_dependabot_branch_needs_only_pr_body_link() -> None:
    assert (
        validation_errors(
            "dependabot/uv/pandas-3.0.6",
            "Bumps pandas.\n\nRefs #285",
            ["chore(deps): bump pandas from 2.3.3 to 3.0.6"],
        )
        == []
    )


def test_dependabot_branch_still_requires_pr_body_link() -> None:
    errors = validation_errors(
        "dependabot/uv/pandas-3.0.6",
        "Bumps pandas.",
        ["chore(deps): bump pandas from 2.3.3 to 3.0.6"],
    )

    assert errors == ["PR body must include Closes/Fixes/Resolves/Refs #123"]


def test_bot_exemption_is_prefix_only() -> None:
    errors = validation_errors("chat/dependabot/x", "Refs #285", ["No link"])

    assert errors == [
        "branch name must include an issue number, for example chat/123-cleanup",
        "commit 1 is missing an issue reference",
    ]
