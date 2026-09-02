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
