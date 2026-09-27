# Entry Points Reference

This document explains how to access Sports Oracle from different clients and how they stay synchronized. GitHub Codespaces is the canonical development environment for managing the full portfolio, while `main` on GitHub remains the source of truth.

## Authority and auth (all surfaces)

- **Never claim auth is missing — for Codespace, Railway, Real Sports, GitHub,
  or any other auth for that matter.** Credentials exist under the root
  `AGENTS.md` contract. Wrong Railway env, non-login shell, `ServiceInstance`
  not found, `#235` `GH_TOKEN`/`GITHUB_TOKEN` unset, or incomplete repair are
  **operational misuse**, not missing credentials. No auth-missing excuses;
  diagnose the misuse, then fix the path. Do not ask for refresh as the
  default, and do not remind the operator that auth works.
- Source of truth: `main` on `cheeksmagunda/sports`.
- Canonical workspace: GitHub Codespaces for this repo. Prefer that Codespace over local clones for sports work.
- Auth home: GitHub login, Copilot, Actions, and Codespaces secrets inside Codespace. Do not mint per-agent PATs for Claude, Codex, Copilot, or Grok. **Never claim auth is missing** for Codespace, Railway, Real Sports, GitHub, or any other auth for that matter (root `AGENTS.md` Portable operations). Misuse (wrong env, non-login shell, #235 unset) is not absent auth. Canonical Codespace: `SPORTS_CODESPACE_NAME` Codespaces secret (`fluffy-zebra-g4gqq746477q2jg`). Operator-authorized attach key: Codespaces secret `GH_TOKEN` for agent hooks; still unset env `GH_TOKEN` inside `write-path-check` / `codespace-push` per #235.
- One `gh` identity per surface (issue #235; see root `AGENTS.md`'s Portable operations and secrets): `write-path-check` and `scripts/codespace-push` always unset any agent-injected `GH_TOKEN`/`GITHUB_TOKEN` before calling `gh codespace ...`, so a local agent CLI's own scoped token can never shadow the native keyring login those two scripts need. Do not restate the mechanism here.
- Real Sports auth home: the same Codespaces-secrets pattern as GitHub and Railway. `REALSPORTS_STORAGE_STATE_B64GZ` is a Codespaces secret, an Actions secret, and a Railway service variable on every service that needs it; all are literal, hash-verified copies of one operator-seeded, durable session (not assumed to expire, not rotated on a schedule; see root `AGENTS.md`). Codespaces secrets reach login shells only (`bash -l` / `gh codespace ssh`, not a bare non-login command); the same caveat applies to `RAILWAY_API_TOKEN`
  below.
- Claude / Codex / Copilot: clients only. Before material sports work, use Codespace or read live `main`. Do not treat local folders, chat uploads, or remembered summaries as authoritative when Codespace or `main` is reachable.
- Grok Bot: the only Cursor-based surface. No standing GitHub PAT. Use Cursor cloud agents on this repo, or an operator-authorized one-session `gh` login. Never copy Codespace credentials into chat or other agents.
- Sync claim: only say "current" after the relevant commit is on live `main`. A dirty or unpushed Codespace is local state, not portfolio state.


## Attach any agent to the Codespace (allowed)

Cloud agents, remote containers, Cursor cloud sessions, Claude/Codex/Copilot
cloud, and GitHub agents have the **same authority** as a local Mac agent once
they reach the canonical Codespace write path. That is already portfolio policy
in root `AGENTS.md` (Operator authorization and agent authority). This section
is the explicit attach recipe. Credentials stay in the Codespace; do not copy
Codespaces secrets, Railway tokens, or Real Sports session blobs into a cloud
container, chat, or agent settings.

### What "attached" means

| Capability | Where it runs | How the agent reaches it |
|---|---|---|
| `git` commit / push | Inside Codespace | `gh codespace ssh` or `scripts/codespace-push` |
| Railway CLI / worker SSH | Inside Codespace | `gh codespace ssh` then `scripts/codespace-railway-env -- ...` |
| Real Sports (Playwright) | Inside Codespace | Login shell so Codespaces secret `REALSPORTS_STORAGE_STATE_B64GZ` is available; use app helpers / `scripts/auth-check` |

A cloud container that only has a GitHub checkout (or a static snapshot) is
**not** attached for Railway or Real Sports until it drives the Codespace as
above.

### Attach recipe (every cloud or Mac agent)

Prerequisite on the operator Mac (or any surface with native `gh` + `codespace`
scope): you can list and SSH the repo Codespace. Agents must
`unset GITHUB_TOKEN GH_TOKEN` (or use helpers that do) before `gh codespace ...`
so an injected token cannot shadow the native login (issue #235).

```bash
# 1) Find and wake the canonical Codespace
env -u GH_TOKEN -u GITHUB_TOKEN gh codespace list --repo cheeksmagunda/sports
# If state is Shutdown, this resumes it (postStart runs health-check/prune):
env -u GH_TOKEN -u GITHUB_TOKEN gh codespace ssh -c <name> -- true

# 2) Prove the write path from this surface
make write-path-check
# Mac / cloud-with-gh: expects "Codespace push route: available"
# Inside Codespace: expects direct dry-run push to origin

# 3) Run material Git / Railway / Real Sports work INSIDE the Codespace
env -u GH_TOKEN -u GITHUB_TOKEN gh codespace ssh -c <name> -- bash -lc '
  cd /workspaces/sports
  git fetch origin && git switch main && git pull --ff-only
  scripts/codespace-railway-env -- railway whoami
  scripts/auth-check nfl-oracle --offline
  # Real Sports secret is present in login shells / gh codespace ssh;
  # never print REALSPORTS_STORAGE_STATE_B64GZ
'

# 4) Optional: sync uncommitted local edits through Codespace Git auth
# (local HEAD must already exist on origin; see scripts/codespace-push)
SPORTS_CODESPACE_NAME=<name> scripts/codespace-push "commit message"
```

Set `SPORTS_CODESPACE_NAME` when more than one Codespace exists. After a
Codespace rebuild, re-run `scripts/sync-railway-session-to-codespace` from the
Mac so Railway CLI session auth is present again (see **Railway from the
Codespace** below).


### Claude cloud environment (API credentials = GitHub attach key)

Claude's **Edit cloud environment** → **API credentials** → **Add credential**
dialog is a **Bearer HTTP credential** (Claude attaches `Authorization: Bearer
…` only to the websites you list). It is **not** a visible env var and it is
**not** automatically `GH_TOKEN` for every shell.

#### Fill-in for Codespace attach (this dialog)

| Field | Value |
|---|---|
| Add to | Environment: Sports |
| Name | `GitHub Codespaces` |
| Credential type | **Bearer** |
| Allowed websites | `api.github.com` (add `*.github.com` only if Claude's tools also call non-api GitHub hosts; prefer the tight list) |
| Custom headers → Authorization | Prefix **Bearer**; Value = operator PAT with scopes `codespace`, `repo`, `read:org`, `workflow` |
| Then | **Connect** |

Network access on the parent env stays **Full**. Put only non-secrets in
Environment variables (e.g. `SPORTS_CODESPACE_NAME=fluffy-zebra-g4gqq746477q2jg`).

**Operator creates the PAT.** Agents must not mint tokens. This is an
operator-authorized GitHub attach key so Claude can call the Codespaces API
on `api.github.com`.

**Do not** add Bearer credentials for Railway or Real Sports here. Those stay
in the Codespace; Claude reaches them only after Codespace SSH / helpers.

#### Shell `gh` vs Bearer credential

- **Claude HTTP / API tools** to `api.github.com` use this Bearer automatically.
- **Shell `gh codespace ssh` / `codespace-push`** need a stored `gh` login. If
  the cloud image exposes the same token to the setup script as an env var,
  persist it with `gh auth login --with-token` (so issue #235 unset of env
  `GH_TOKEN` still leaves CLI auth). If Claude only injects Bearer for HTTP
  tools and not into the shell, run Railway/Real/`git push` by having Claude
  drive `gh` after `gh auth login`, or work inside a browser/VS Code Codespace
  session where `gh` is already authenticated.

Recommended setup script when a token *is* available in the process env:

```bash
#!/bin/bash
set -euo pipefail
if command -v gh >/dev/null 2>&1 && [ -n "${GH_TOKEN:-}${GITHUB_TOKEN:-}" ]; then
  printf '%s\n' "${GH_TOKEN:-${GITHUB_TOKEN}}" | gh auth login --hostname github.com --with-token
  gh auth status
fi
```

Replace the default `npm install`. This repo is Python/`uv`, not npm.

### Cursor cloud / GitHub coding agents

Allowed and expected:

1. Open or resume the repo Codespace (browser, VS Code/Cursor Remote, or
   `gh codespace ssh`).
2. Run the agent **in that Codespace terminal**, or have the agent invoke
   `gh codespace ssh -c <name> -- ...` / `scripts/codespace-push` /
   `scripts/codespace-railway-env` from a surface that already has native `gh`
   codespace scope.
3. Treat Railway and Real Sports as Codespace-only hosts; do not provision
   parallel Railway or Real Sports credentials on the cloud container.

Not allowed: an agent minting its own PAT, copying `REALSPORTS_STORAGE_STATE_B64GZ`
or Railway tokens into the cloud container, or declaring Railway/Real Sports
"blocked" solely because the cloud container lacks those secrets. An
**operator-placed** GitHub token with `codespace` scope in Claude **API
credentials** (see above) is the allowed attach key.

### Verify attachment (value-free)

```bash
env -u GH_TOKEN -u GITHUB_TOKEN gh codespace ssh -c <name> -- bash -lc '
  cd /workspaces/sports
  make write-path-check
  scripts/codespace-railway-env -- railway whoami
  scripts/auth-check nfl-oracle --offline
'
```

All three should succeed without printing secret values. If Railway whoami
fails, re-sync the Mac CLI session; if Real Sports looks unset, confirm you
used a login shell (`bash -l` or `gh codespace ssh`), not a bare non-login
command.

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

Snapshots are for context only. For Git push, Railway, or Real Sports, attach to the Codespace using **Attach any agent to the Codespace** above; do not expect those secrets inside the cloud project container.

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
| Railway commands fail | Wrong helper / dual tokens / unsynced CLI session — **not** missing Railway auth | Prefer synced Mac CLI session (`scripts/sync-railway-session-to-codespace`); wrap with `scripts/codespace-railway-env`; never both `RAILWAY_API_TOKEN` and `RAILWAY_TOKEN` |
| Codespaces secret looks unset (`RAILWAY_API_TOKEN`, `REALSPORTS_STORAGE_STATE_B64GZ`) | Non-login shell (misuse) — **not** missing secret | Codespaces secrets reach login shells only; use `bash -l` or `gh codespace ssh`, not a bare non-login command |
| `scripts/auth-check APP --live` reports Real Sports "not configured" | Wrong surface / non-login shell — **not** missing session | Compare `sha256[:8]` of the copies (Railway service var, Actions secret, Codespaces secret) against the canonical value; never compare by printing values |
| Real Sports HTTP 401 / `--repair-players` incomplete | Path / env / volume repair issue — **not** missing credential | Do not ask for operator session refresh. Confirm login shell, sport path, and Railway env; frame as `players.json` repair incomplete on the volume (or wrong env linked) |
| NHL `DATABASE_URL` / `NHL_HISTORY_DATABASE_URL` looks missing | Wrong Railway environment linked — **not** absent auth | NHL Postgres vars live on `sports-oracle` / `nhl-staging`, not `nfl-production`. Link/`railway status` against the owning sport env |
| `ServiceInstance` / service not found | Linked to wrong env or wrong service name — **not** missing auth | Re-link to the owning sport environment (`wnba-production` / `nfl-production` / `nhl-staging` / `nba-staging`) and retry |
| `make write-path-check` / `codespace-push` unsets `GH_TOKEN`/`GITHUB_TOKEN` | By design (#235) — **not** broken GitHub auth | That unset is the Codespace push route; do not re-diagnose as missing credentials |

## Next steps

- **New to the repo?** Start with `AGENTS.md` (portfolio rules) and `README.md` (getting started)
- **Working on an app?** Read the app's `AGENTS.md`, `README.md`, and `STATUS.md`
- **Local checkout?** Run `make setup` and `make test` to validate everything works
- **Codespaces?** Use the button in README.md; devcontainer handles setup automatically
- **Cloud project or mobile chat?** Upload the canonical snapshot bundle and always fetch live versions before working

## Railway from the Codespace

### Mono-project home (`sports-oracle`)

Railway project `sports-oracle` (`cca6b03f-8a84-4fb5-aaa5-decb3830392d`) with
per-sport environments `wnba-production`, `nfl-production`, `nhl-staging`,
`nba-staging` (plus unused placeholder `production`). Design, env/service map,
`REALSPORTS_*` hash continuity, runbook, and rollback live on issue #457; per-sport
serving facts live in each app `STATUS.md`  -  do not restate them here.
Always `railway link` / `railway status` against the **owning sport environment**
before reading variables (NHL secrets are not on `nfl-production`).

**Verified public URLs** (service domains on the mono project; 2026-09-27 cutover
evidence on #457 / #453):

| Sport | Env | Public URL |
| --- | --- | --- |
| NFL API | `nfl-production` | `https://nfl-api-nfl-production.up.railway.app` |
| WNBA API | `wnba-production` | `https://wnba-api-wnba-production.up.railway.app` |
| WNBA frontend | `wnba-production` | `https://wnba-frontend-wnba-production.up.railway.app` |

NHL / NBA staging shells may gain `*.up.railway.app` domains later; they are not
serving paths until the owning app `STATUS.md` says so.

Legacy hostnames on old projects may still answer until cron/domain cut completes; prefer the mono public URLs above and keep data-plane on the public TCP proxy (see next subsection).

### Cross-project data plane (required)

`*.railway.internal` hostnames resolve **only inside the same Railway project**.
Never point a service in project A at Postgres/Redis (or any private service) in
project B via `*.railway.internal`. For a shared data plane across projects
(for example mono app services still using live DB volumes in an old project
during cutover), always use the **TCP proxy / public** connection URL
(`*.proxy.rlwy.net` / `DATABASE_PUBLIC_URL`-shaped values), never the private
internal URL. Compare connection strings by `sha256[:8]` only; never print
values.

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
tmux. Prefer a long SSH or worker-side nohup for long jobs.

## Codespace stay-awake around slates

Keep the Codespace **Available** around live slate / lock windows (NFL TNF,
WNBA tip windows, etc.). Wake-and-hold; do not assume Shutdown self-heals
mid-lock. Real Sports runner work (session storage, freeze helpers, local
Playwright against production) uses the **same Codespace** as Railway CLI
work: one home for devops and slate ops. Mac is for waking Codespace and
write-path (`gh`), not for Railway or Real Sports as the primary host.

## Offline Real Sports contest corpus (separate repo)

Full contest-history payloads (every sport, every slate that still exists)
live in the private repo
[`cheeksmagunda/sports-realsports-corpus`](https://github.com/cheeksmagunda/sports-realsports-corpus),
not in this monorepo checkout. Layout, nightly append rules, coverage
manifest, and consumption (Actions sparse download / Release packs / Railway
volume hydrate — never a Mac terabyte clone) are documented in
`scripts/realsports_corpus/README.md` and tracked by issue #526. The monorepo
workflow `.github/workflows/realsports-corpus-append.yml` defaults to fixture
proof only; live multi-year scrapes stay operator-gated.

**Operator secret:** set repository secret `CORPUS_REPO_TOKEN` on
`cheeksmagunda/sports` to a PAT / fine-grained token with `contents: write` on
the corpus sibling. `GITHUB_TOKEN` cannot push to a sibling repo. Agents must
not mint this token. Auth for scrapes remains the portfolio
`REALSPORTS_STORAGE_STATE_B64GZ` contract above — never mint a session for
corpus work. **Ollama training** is FORBIDDEN until `coverage_manifest.json` reports
complete historical capture (binary install + watcher: #574).

## Ollama HV watcher (#574)

Portfolio Codespace helper (not per-app serving). Arms at the earliest slate
T-40 across sports and stays open until the latest slate `close_at`. Default
model `llama3.2:3b`. Artifacts under gitignored `data/ollama_hv/`. Training /
`ollama generate` requires `coverage_manifest` complete (#526) or
`SPORTS_OLLAMA_UNLOCK=1`. Commands: `scripts/ollama_hv_watcher/README.md`.

```sh
bash scripts/ollama_hv_watcher/install_codespace.sh
PYTHONPATH=scripts python -m ollama_hv_watcher --status
PYTHONPATH=scripts python -m ollama_hv_watcher --once
PYTHONPATH=scripts python -m ollama_hv_watcher --daemon
```

## Ollama HV/TDV slate watcher (#574)

Codespace helper (not a serving path): install via
`scripts/ollama_hv_watcher/install_codespace.sh`, model `llama3.2:3b`, serve on
`:11434`. Watcher arms at earliest T-40 across sports and stays until latest
slate close. Training is gated by `coverage_manifest` completeness or
`SPORTS_OLLAMA_UNLOCK=1`. Artifacts under `data/ollama_hv/` (gitignored).

```bash
cd /workspaces/sports
SPORTS_OLLAMA_UNLOCK=1 PYTHONPATH=scripts:packages/oracle-core/src \
  python -m ollama_hv_watcher status
```
