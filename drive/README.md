# Document Drive

`drive/` is a shared workspace for temporary files, task briefs, agent handoffs, research inventories, and static one-time use documents.

Because the repository on `main` is the single source of truth for all access points (Copilot CLI, Copilot coding agent, Claude Code, GitHub App, Codespaces), putting working documents here ensures that any agent on any surface can read them without the operator needing to copy/paste content.

## Conventions

- **Task Briefs**: `YYYY-MM-DD-<slug>.md`. Start with a header containing:
  ```text
  # <Task title>
  Status: draft | ready | running | done | cancelled
  Created: YYYY-MM-DD
  Owner: <operator or session>
  ```
- **Handoffs & Working Files**: Name clearly (e.g., `YYYY-MM-DD-inventory.md` or `feature-x-handoff.md`).
- **Cleanup**: Delete or archive files when the task is complete or the handoff is no longer needed. Do not leave stale state here.
- **No Secrets**: Never store credentials, API keys, or Real Sports sessions in this directory.