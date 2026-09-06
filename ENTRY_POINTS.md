# Entry Points Reference

This document explains how to access Sports Oracle from different clients and how they stay synchronized. GitHub Codespaces is the canonical development environment for managing the full portfolio, while `main` on GitHub remains the source of truth.

## Authority and auth (all surfaces)

- Source of truth: `main` on `cheeksmagunda/sports`.
- Canonical workspace: GitHub Codespaces for this repo. Prefer that Codespace over local clones for sports work.
- Auth home: GitHub login, Copilot, Actions, and Codespaces secrets inside Codespace. Do not mint per-agent PATs for Claude, Codex, Copilot, or Grok.
- Claude / Codex / Copilot: clients only. Before material sports work, use Codespace or read live `main`. Do not treat local folders, chat uploads, or remembered summaries as authoritative when Codespace or `main` is reachable.
- Grok Bot: the only Cursor-based surface. No standing GitHub PAT. Use Cursor cloud agents on this repo, or an operator-authorized one-session `gh` login. Never copy Codespace credentials into chat or other agents.
- Sync claim: only say "current" after the relevant commit is on live `main`. A dirty or unpushed Codespace is local state, not portfolio state.

## Quick-start by entry point

### GitHub Codespaces (browser, app, or forwarded editor)

1. Click **Code > Codespaces > Create codespace on main**, or use the badge in README.md
2. The devcontainer automatically starts PostgreSQL, Redis, and runs `make codespaces-smoke`
3. Use the integrated terminal like a local checkout:

```bash
make setup
make test-app APP=nfl-oracle
cd nfl-oracle && make test
```

**Sync status:** Live workspace. It becomes portfolio-current only after the relevant commit lands on `main`.

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

**Sync status:** Live checkout. It becomes portfolio-current only after the relevant commit lands on `main`.

### Copilot app, GitHub, and mobile

1. Open the repo folder (or clone `cheeksmagunda/sports`)
2. Open Copilot composer panel
3. Reference project files directly; Copilot sees your working tree
4. Use integrated terminal for `make` commands

**Sync status:** Live client when attached to the checkout, Codespace, or GitHub repository. Static chat context still needs refresh, and only `main` is portfolio-current.

### Claude Code CLI (local terminal)

```bash
cd /workspaces/sports      # Codespaces
# or: cd ~/Developer/sports # Mac checkout
# Claude Code reads the repo directly
claude code
```

**Sync status:** Live client if the CLI reads from your checkout or Codespace. Only `main` is portfolio-current.

### Claude app, web, and mobile

Use Claude with a live GitHub connector, Codespace, or synchronized local checkout when possible. Claude is a client, not a separate GitHub credential home. If the Claude client is using uploaded project files or pasted context, use the cloud project snapshot rules below.

**Sync status:** Live client with a connector; otherwise static snapshot. Only `main` is portfolio-current.

### Codex CLI or app

```bash
cd /workspaces/sports      # Codespaces
# or: cd ~/Developer/sports # Mac checkout
# Codex reads the repo directly when launched from the checkout or Codespace
codex
```

Use Codex terminal, desktop app, web, or mobile with the live repository when available. Codex is a client, not a separate GitHub credential home. If the client only has uploaded project files or pasted context, treat it as a static snapshot.

**Sync status:** Live client when attached to the checkout, Codespace, or GitHub repository; otherwise static snapshot. Only `main` is portfolio-current.

### Grok app, web, mobile, or grokbot

Use Grok against the GitHub repository or Codespace when that connector is available. Grok Bot is the only Cursor-based surface: use Cursor cloud agents on this repo or an operator-authorized one-session `gh` login, with no standing PAT. If Grok is working from pasted files, uploaded docs, or a knowledge base, refresh the snapshot before each material task and execute changes through a synchronized entry point.

**Sync status:** Live client with a connector; otherwise read-only or static snapshot. Only `main` is portfolio-current.

### Cloud project snapshots

Use this for Claude projects, Codex projects, Copilot reusable chat/project context, Grok knowledge bases, and mobile chats that cannot read the live repository directly.

1. Create or refresh the project with the canonical snapshot bundle:
   - Root `AGENTS.md`, `README.md`, `Makefile`, and `pyproject.toml`
   - `.devcontainer/` and `.github/workflows/`
   - Each application's `AGENTS.md`, `README.md`, and `STATUS.md`
   - Do not upload a root `STATUS.md`; the root has none

2. When starting work:
   - Ask the agent to fetch the live repository version from GitHub
   - Cross-check with the live file; treat live as authoritative
   - Note any discrepancies between snapshot and live

**Sync status:** Static snapshot, may be stale. Always fetch the live version before acting.

### Manual local session export

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

# Use in any local agent session that cannot read the checkout directly
```

**Sync status:** Manual. Re-export from the live repository before each session.

## The monorepo structure (same across all entry points)

```
cheeksmagunda/sports/
├── packages/oracle-core/        Domain-free shared platform
├── wnba-oracle/                 WNBA app (models, features, contests, etc.)
├── nfl-oracle/                  NFL app (models, features, contests, etc.)
├── nba-oracle/                  NBA app (models, features, contests, etc.)
├── nhl-oracle/                  NHL app (models, features, contests, etc.)
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
make test-app APP=nba-oracle
make test-app APP=nhl-oracle
make test-integration        # Requires PostgreSQL + Redis
make lint                    # Ruff check and format
make typecheck               # mypy
make check-boundaries        # Verify app -> core dependency direction
make build                   # Build app container images

# Auth checks (no secrets printed)
scripts/auth-check wnba-oracle --offline
scripts/auth-check nfl-oracle --offline
```

### External CLI tools (operator/environment-dependent)

```bash
# GitHub CLI — reads native credential store
gh pr list
gh codespace list

# Railway CLI — available when installed in current surface
# If auth fails, verify RAILWAY_TOKEN validity and project access scope
railway link
railway status
# See nfl-oracle/STATUS.md for Railway project link notes
```

### App-specific (from the app directory)

```bash
cd nfl-oracle && make test
cd wnba-oracle && make test
cd nba-oracle && make test
cd nhl-oracle && make test
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
`README.md`, application `STATUS.md`, `Makefile`, `pyproject.toml`,
`.devcontainer/`, `.github/workflows/`). When flagged, the operator re-uploads
snapshots to any configured static project:

- Claude projects and chats
- Codex projects and chats
- Copilot reusable project/chat context
- Grok knowledge bases and chats

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
- Mint per-agent PATs for Claude, Codex, Copilot, or Grok
- Copy Codespaces secrets into chat, local folders, Cursor, or other agents
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
| Claude/Codex/Copilot/Grok snapshot differs from repo | Snapshot drifted | Fetch live via GitHub connector |
| `make setup` fails | Locked deps changed | Check if you're on latest `main` |
| Tests fail in CLI but pass in Codespace | Different Python/uv version | Run `uv sync --frozen --reinstall` |
| Railway commands fail | CLI not authenticated | Run `railway login` or check `RAILWAY_TOKEN` |

## Next steps

- **New to the repo?** Start with `AGENTS.md` (portfolio rules) and `README.md` (getting started)
- **Working on an app?** Read the app's `AGENTS.md`, `README.md`, and `STATUS.md`
- **Local checkout?** Run `make setup` and `make test` to validate everything works
- **Codespaces?** Use the button in README.md; devcontainer handles setup automatically
- **Cloud project or mobile chat?** Upload the canonical snapshot bundle and always fetch live versions before working
