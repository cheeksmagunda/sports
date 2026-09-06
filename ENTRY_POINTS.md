# Entry Points Reference

This document explains how to access Sports Oracle from different clients and how they stay synchronized.

## Quick-start by entry point

### GitHub Copilot CLI (terminal)

```bash
# Clone the repo (or open existing)
gh repo clone cheeksmagunda/sports
cd sports

# Install dependencies
make setup

# Run tests
make test

# Work on a branch
git checkout -b my-feature
# ... make changes ...
git push origin my-feature
gh pr create
```

**Sync status:** Always current. Copilot CLI reads the repository directly.

### GitHub Codespaces (browser or local)

1. Click **Code > Codespaces > Create codespace on main**, or use the badge in README.md
2. The devcontainer automatically starts PostgreSQL, Redis, and runs `make codespaces-smoke`
3. Use the integrated terminal like a local checkout:

```bash
make setup
make test-app APP=nfl-oracle
cd nfl-oracle && make test
```

**Sync status:** Always current. Codespaces runs the live repository.

### Copilot Desktop App

1. Open the repo folder (or clone `cheeksmagunda/sports`)
2. Open Copilot composer panel
3. Reference project files directly; Copilot sees your working tree
4. Use integrated terminal for `make` commands

**Sync status:** Always current. Desktop reads the live checkout.

### Claude Code CLI (local terminal)

```bash
cd /workspaces/sports
# Claude Code reads the repo directly
claude code
```

**Sync status:** Always current if the CLI reads from your checkout.

### Claude.ai web session (with project)

1. Create a Claude project or upload static files:
   - `AGENTS.md`, `README.md`, `STATUS.md` (root and each app)
   - `Makefile`, `pyproject.toml`, `.devcontainer/Dockerfile`
   - Application-specific AGENTS.md for NFL and WNBA

2. When starting work:
   - Ask Claude to fetch the live repository version from GitHub
   - Cross-check with the live file; treat live as authoritative
   - Note any discrepancies between snapshot and live

**Sync status:** Static snapshot, may be stale. Always fetch the live version before acting.

### ChatGPT project

Same as Claude.ai: upload snapshots, fetch live versions when working.

**Sync status:** Static snapshot, may be stale. Always fetch the live version before acting.

### Grok web session (read-only)

1. Access the repository view on GitHub
2. Reference file contents in the chat
3. Or upload a snapshot of `AGENTS.md` and `README.md`

**Sync status:** Read-only or static snapshot. Use for research only; execute work through a sync'd entry point.

### Grok local session

Export relevant docs as markdown or text, include in context:

```bash
# Example: prepare context file
{
cat /workspaces/sports/AGENTS.md
echo "---"
cat /workspaces/sports/README.md
echo "---"
cat /workspaces/sports/nfl-oracle/AGENTS.md
} > /tmp/sports-context.md

# Use in local Grok session
```

**Sync status:** Manual. Re-export from the live repository before each session.

## The monorepo structure (same across all entry points)

```
cheeksmagunda/sports/
├── packages/oracle-core/        Domain-free shared platform
├── wnba-oracle/                 WNBA app (models, features, contests, etc.)
├── nfl-oracle/                  NFL app (models, features, contests, etc.)
├── scripts/                      Portfolio operations (auth, secrets, CI)
├── AGENTS.md                     Portfolio instructions for all agents
├── README.md                     Portfolio overview
├── Makefile                      Shared build targets
├── pyproject.toml                Workspace dependencies
└── .devcontainer/                Codespaces environment
```

## Shared commands (work the same everywhere)

### Setup and verification

```bash
make setup                   # Install locked dependencies
make test                    # Run all offline tests
make test-core               # Test oracle-core only
make test-app APP=wnba-oracle
make test-app APP=nfl-oracle
make test-integration        # Requires PostgreSQL + Redis
make lint                    # Ruff check and format
make typecheck               # mypy
make check-boundaries        # Verify app -> core dependency direction
make build                   # Build app container images
```

### App-specific (from the app directory)

```bash
cd nfl-oracle && make test
cd wnba-oracle && make test
```

### CI/CD

All entry points can trigger CI by:
- Pushing to a branch: `git push origin my-feature`
- Opening a PR: `gh pr create`
- GitHub Actions runs the shared checks automatically

Merge autonomy: when checks are green and work is in scope, agents merge directly.

## Keeping snapshots current

**When do snapshots need updating?**

A scheduled workflow flags changes to sync-critical files (any `AGENTS.md`,
`README.md`, `STATUS.md`, `Makefile`, `pyproject.toml`, `.devcontainer/`,
`.github/workflows/`). When flagged, the operator re-uploads snapshots to:

- Claude.ai projects
- ChatGPT projects
- Grok knowledge bases (if used)

**Before you act on a snapshot:**

1. Check the GitHub repository for the live version
2. Compare snapshot vs. live
3. If they differ, mention the discrepancy and use the live version
4. Snapshots are convenience only; live repository is authoritative

## Access token and credential handling

**CLI credential stores (preferred):**
- Native `gh` CLI — GitHub authentication
- Railway CLI — Railway.app authentication
- `SOPS`/`age` — optional encrypted at-rest for environment values

**Do not:**
- Copy credentials into files or environment
- Log token values
- Commit `.env` files
- Use plaintext secret storage

**Do:**
- Let CLIs manage their own credential stores
- Supply secrets via process environment for commands that need them
- Use `scripts/with-secrets APP -- <command>` for encrypted local values
- Verify auth with `scripts/auth-check APP --offline` (no secrets printed)

## Troubleshooting sync issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| Codespace sees old files after PR merge | Needs refresh | `git pull origin main` in terminal |
| Claude/ChatGPT snapshot differs from repo | Snapshot drifted | Fetch live via GitHub connector |
| `make setup` fails | Locked deps changed | Check if you're on latest `main` |
| Tests fail in CLI but pass in Codespace | Different Python/uv version | Run `uv sync --frozen --reinstall` |
| Railroad.app (Railway) commands fail | CLI not authenticated | Run `railway login` or check `RAILWAY_TOKEN` |

## Next steps

- **New to the repo?** Start with `AGENTS.md` (portfolio rules) and `README.md` (getting started)
- **Working on an app?** Read the app's `AGENTS.md`, `README.md`, and `STATUS.md`
- **Local checkout?** Run `make setup` and `make test` to validate everything works
- **Codespaces?** Use the button in README.md; devcontainer handles setup automatically
- **Web session (Claude/ChatGPT)?** Upload snapshots and always fetch live versions before working
