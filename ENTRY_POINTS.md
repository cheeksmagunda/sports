# Entry Points Reference

This document explains how to access Sports Oracle from different clients and how they stay synchronized. GitHub Codespaces is the canonical development environment for managing the full portfolio, while `main` on GitHub remains the source of truth.

## Authority and auth (all surfaces)

- Source of truth: `main` on `cheeksmagunda/sports`.
- Canonical workspace: GitHub Codespaces for this repo. Prefer that Codespace over local clones for sports work.
- Auth home: GitHub login, Copilot, Actions, and Codespaces secrets inside Codespace. Do not mint per-agent PATs for Claude, Codex, Copilot, or Grok.
- One `gh` identity per surface (issue #235; see root `AGENTS.md`'s Portable operations and secrets): `write-path-check` and `scripts/codespace-push` always unset any agent-injected `GH_TOKEN`/`GITHUB_TOKEN` before calling `gh codespace ...`, so a local agent CLI's own scoped token can never shadow the native keyring login those two scripts need. Do not restate the mechanism here.
- Real Sports auth home: the same Codespaces-secrets pattern as GitHub and Railway. `REALSPORTS_STORAGE_STATE_B64GZ` is a Codespaces secret, an Actions secret, and a Railway service variable on every service that needs it; all are literal, hash-verified copies of one operator-seeded, durable session (not assumed to expire, not rotated on a schedule; see root `AGENTS.md`). Codespaces secrets reach login shells only (`bash -l` / `gh codespace ssh`, not a bare non-login command); the same caveat applies to `RAILWAY_API_TOKEN`
  below.
- Claude / Codex / Copilot: clients only. Before material sports work, use Codespace or read live `main`. Do not treat local folders, chat uploads, or remembered summaries as authoritative when Codespace or `main` is reachable.
- Grok Bot: the only Cursor-based surface. No standing GitHub PAT. Use Cursor cloud agents on this repo, or an operator-authorized one-session `gh` login. Never copy Codespace credentials into chat or other agents.
- Sync claim: only say "current" after the relevant commit is on live `main`. A dirty or unpushed Codespace is local state, not portfolio state.

## Quick-start by entry point

### GitHub Codespaces (browser, app, or forwarded editor)

1. Click **Code > Codespaces > Create codespace on main**, or use the badge in README.md
2. The devcontainer starts PostgreSQL and Redis, then on creation installs the
   locked workspace and the Playwright/Chromium browser Real Sports needs
   (`scripts/devcontainer-postcreate.sh`). `make codespaces-smoke` is a
   separate CI check (`.github/workflows/devcontainer-smoke.yml`) that
   verifies a fresh build stays buildable; it does not run automatically
   inside a live Codespace.
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

For Mac editing with Codespace-authenticated Git operations, run
`SPORTS_CODESPACE_NAME=<name> scripts/codespace-push "message"` from the local
checkout. Your local worktree diff is transferred to the Codespace, where
commit and push execute. Credentials remain in the Codespace.

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
   - Root `AGENTS.md`, `README.md`, curated `OVERVIEW.md`, generated `FILES.md`, `Makefile`, and `pyproject.toml`
   - `.devcontainer/` and `.github/workflows/`
   - Each application's `AGENTS.md`, `README.md`, and `STATUS.md`
   - Do not upload a root `STATUS.md`; the root has none
   - Regenerate `FILES.md` with `scripts/generate_file_manifest.py` whenever the tracked tree changes

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
scripts/auth-check nba-oracle --offline
scripts/auth-check nhl-oracle --offline

# --live adds a value-free Real Sports structure check for wnba-oracle and
# nfl-oracle (the only two applications that use it today):
scripts/auth-check wnba-oracle --live
scripts/auth-check nfl-oracle --live
```

### External CLI tools (operator/environment-dependent)

```bash
# GitHub CLI — reads native credential store
gh pr list
gh codespace list

# Railway CLI — available when installed in current surface
# If auth fails, verify the token kind: RAILWAY_API_TOKEN (account/workspace)
# or RAILWAY_TOKEN (project, one environment); never both at once
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

A workflow flags changes to sync-critical files (any `AGENTS.md`, `README.md`,
application `STATUS.md`, root `OVERVIEW.md`, generated `FILES.md`, `Makefile`,
`pyproject.toml`, `.devcontainer/`, `.github/workflows/`). When flagged, the
operator re-uploads snapshots to any configured static project:

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
| Railway commands fail | CLI not authenticated | Prefer synced Mac CLI session (`scripts/sync-railway-session-to-codespace`); wrap with `scripts/codespace-railway-env`; never both `RAILWAY_API_TOKEN` and `RAILWAY_TOKEN` |
| Codespaces secret looks unset (`RAILWAY_API_TOKEN`, `REALSPORTS_STORAGE_STATE_B64GZ`) | Non-login shell | Codespaces secrets reach login shells only; use `bash -l` or `gh codespace ssh`, not a bare non-login command |
| `scripts/auth-check APP --live` reports Real Sports "not configured" | Session not propagated to this surface | Compare `sha256[:8]` of the copies (Railway service var, Actions secret, Codespaces secret) against the canonical value; never compare by printing values |

## Next steps

- **New to the repo?** Start with `AGENTS.md` (portfolio rules) and `README.md` (getting started)
- **Working on an app?** Read the app's `AGENTS.md`, `README.md`, and `STATUS.md`
- **Local checkout?** Run `make setup` and `make test` to validate everything works
- **Codespaces?** Use the button in README.md; devcontainer handles setup automatically
- **Cloud project or mobile chat?** Upload the canonical snapshot bundle and always fetch live versions before working

## Railway from the Codespace

All Railway mutations and worker SSH (link, restart, redeploy, `train --force`,
logs, variable changes) run **from inside the GitHub Codespace**, after
`railway whoami` shows the operator account (Cheeks Magunda). Do not run
Railway from the operator Mac, and do not use `SPORTS_ALLOW_LOCAL_RAILWAY` as
the normal path.

### Canonical auth: synced Mac CLI session

Canonical Codespace Railway auth is a **synced Mac `~/.railway` CLI OAuth
session** (accessToken / refreshToken), not the Codespaces secret. The Mac
session (`railway whoami` as Cheeks Magunda) is the source of truth. Sync it
into the Codespace with:

```bash
# On the operator Mac (after Codespace create or rebuild):
scripts/sync-railway-session-to-codespace
# or: scripts/sync-railway-session-to-codespace fluffy-zebra-g4gqq746477q2jg
```

That packs `$HOME/.railway` (locks excluded) into the Codespace `$HOME/.railway`,
chmods private, and links `nfl-oracle-staging` / `production` /
`nfl-oracle-worker` under `/workspaces/sports` via the helper below.

The Codespaces secret `RAILWAY_API_TOKEN` may still be present (and even look
valid by length) but often returns Unauthorized. **Do not ask the operator to
mint a new API token when the Mac CLI session works.** Re-sync the session
instead. Only refresh `RAILWAY_API_TOKEN` if no CLI session can be restored.

### Headless SSH gotcha (read this)

`gh codespace ssh` often has **no** `RAILWAY_*` in the process environment even
with `bash -l`. Codespaces still writes user secrets to
`/workspaces/.codespaces/shared/.env-secrets`. Do not conclude "no token" from
an empty `printenv`. Also: if both `RAILWAY_API_TOKEN` (account) and
`RAILWAY_TOKEN` (project/CI) are set, the CLI returns Unauthorized. Never keep
both. Do not delete the GitHub Actions project `RAILWAY_TOKEN` used by CI.

**Mandatory helper before any Railway CLI work:**

```bash
scripts/codespace-railway-env -- railway whoami
scripts/codespace-railway-env -- railway status
```

The helper prefers a working `~/.railway` CLI session first (when config has
access/refresh tokens), tries `RAILWAY_API_TOKEN` from the environment or
`.env-secrets` only if the session is missing or whoami fails, always unsets
`RAILWAY_TOKEN`, asserts `whoami`, logs which path won (never prints token
values), then execs your command. If both fail, re-sync the Mac CLI session
(`scripts/sync-railway-session-to-codespace`); refresh the Codespaces
`RAILWAY_API_TOKEN` only as a last resort.

Pattern:

1. Wake the Codespace with Mac `gh` (`gh codespace ssh -c <name> --` or the
   VS Code / Cursor remote). After a rebuild, re-run
   `scripts/sync-railway-session-to-codespace` from the Mac.
2. Run Railway only through `scripts/codespace-railway-env -- ...` (or
   `eval "$(scripts/codespace-railway-env --print-exports)"` then `railway`).
3. If `railway ssh` fails on host key, register the Codespace host key with
   `railway ssh keys add` (or import) before retrying.
4. Worker CLIs live under `/opt/venv/bin` on the service image. Example NFL
   forced retrain:

```bash
scripts/codespace-railway-env -- railway ssh --service nfl-oracle-worker -- \
  bash -lc 'export PATH=/opt/venv/bin:$PATH; nfl-pipeline train --force'
```

Do not rely on `railway ssh --session` / tmux unless the worker image has
tmux. Prefer a long SSH or worker-side nohup for long jobs.## Codespace stay-awake around slates

Keep the Codespace **Available** around live slate / lock windows (NFL TNF,
WNBA tip windows, etc.). Wake-and-hold; do not assume Shutdown self-heals
mid-lock. Real Sports runner work (session storage, freeze helpers, local
Playwright against production) uses the **same Codespace** as Railway CLI
work: one home for devops and slate ops. Mac is for waking Codespace and
write-path (`gh`), not for Railway or Real Sports as the primary host.

