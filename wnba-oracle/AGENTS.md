# AGENTS.md (WNBA Oracle)

Operating manual for any agent working on this project: interactive Claude
Code sessions on the operator's machine, and the two scheduled cloud
routines. The original unattended-build handoff is finished; its logs were
removed in the 2026-07-01 doc cleanup and live in git history.

## Build state (D78, 2026-06-07)

The system is fully live. All major phases are wired and deployed on Railway.

Active model: `picker_e2ced9ec_1780873338.pkl` (SHA `94f8e8606dab...`), trained
on a 13,002-row corpus with team_pace + opponent DvP enrichment (D77). The
LightGBM multi-task heads (minutes x per-minute-rate, cohort F) are wired into
the `job2` Tier-0 prediction path (D69), with confirmed-starter multiplier (D71),
sportsbook prop-signal multiplier (D78, PROP_SIGNAL_SCALE=0.3), late re-freeze
at 23:00 UTC (D75), availability model (D73), lineup anchor floor of 2 (D57),
game-stack bonus (D70/R3), boost caps (D70/R2), n_field=500 (D76), and
targeted pool fallback for unmatched players (D72). Walk-forward corr 0.554 vs
boost heuristic 0.246. Production training command: `oracle-train --corpus-mode
both`. See STATUS.md for current state; decision history lives in git.

## Autonomy

- Never stop to ask the human a question. Decide, act, and log the
  reasoning in the commit message.
- Dependencies: you are pre-authorized to add any dependency that is a
  well-known PyPI or npm package, permissively licensed (MIT, BSD, Apache),
  and needed for a real capability. Do not pause to confirm.
- "Research" or "open question" means decide and log, never ask.

## Work hygiene

- Read files before editing. Preserve existing style.
- Commit after every working increment with a descriptive message.
- Keep code grep-able and consistent. Remove dead code and scratch files.
- Docs policy (2026-07-01 cleanup): only README.md, STATUS.md, and this file
  exist. Decision history goes in commit messages; operational history goes
  in the ops GitHub issues; do not reintroduce DECISIONS.md, NEEDS_CLAUDE.md,
  RESULTS.md, or other markdown ledgers.

## Output style

- No em dashes. Vary sentence length. No emojis.
- Distinguish verified facts from synthesized reasoning in commit messages
  and issue comments.

## Credentials and authorization

Architecture: Single source of truth per layer. All development happens in
Claude Code.

**Local (Claude Code):** `.claude/settings.local.json` (gitignored,
machine-local) holds 5 credentials in its `env` block. Claude Code exports
them into the session environment, so every tool run sees them.

**Production (Railway):** The same credentials plus all config (80+ env vars).
Config values (DATABASE_URL, REDIS_URL, model artifact SHA, optimizer settings,
etc.) live on Railway only and are not needed locally.

The owner has granted blanket authorization to use these credentials for any
operation this project legitimately requires. Do not pause to re-confirm.

**Local credentials (.claude/settings.local.json env block):**
- `GITHUB_TOKEN`: git + `gh` auth
- `RAILWAY_WORKSPACE_TOKEN`: workspace token for scripted GraphQL (rwgql.sh)
- `ODDS_API_KEY`: The Odds API requests
- `REAL_SPORTS_USERNAME` / `REAL_SPORTS_PASSWORD`: Real Sports login

**Cloud scheduled agents (claude.ai routines):** `.claude/credentials.env`
(committed; private repo) holds only `RAILWAY_WORKSPACE_TOKEN` and
`GITHUB_TOKEN`. Everything else the routines need is fetched at runtime via
Railway GraphQL. The cloud container cannot reach the Postgres TCP proxy
(non-HTTP outbound blocked) -- routines must use the api service HTTP
endpoints and Railway logs, never psql. Deleting credentials.env breaks the
routines' bootstrap (this caused the 2026-06-28..07-02 blind-audit incident,
issue #10).

### GitHub / git

The repo's git credential helper reads `$GITHUB_TOKEN` directly. Plain
`git push origin main` works without any prefix. `gh` works as-is: it picks
up `$GITHUB_TOKEN` from the session env, and the same PAT is also stored in
the macOS keyring for use outside Claude Code.

### Railway

Two auth paths, deliberately separate:

1. **CLI + MCP tools (interactive):** user OAuth from `railway login`, stored
   in `~/.railway/config.json`. `railway whoami`, `railway logs`, and the
   Railway MCP server all use this. It only works because no `RAILWAY_TOKEN`
   env var is exported -- the CLI prefers that variable over the stored login
   and a workspace token in it breaks everything. Never add `RAILWAY_TOKEN`
   back to the settings env block.
2. **Scripted GraphQL:** `scripts/rwgql.sh` reads `RAILWAY_WORKSPACE_TOKEN`
   and talks to backboard.railway.com directly. Use it for automation
   (variable upserts, redeploys) where the CLI is awkward:

```bash
scripts/rwgql.sh '<graphql query>'
scripts/rwgql.sh '<graphql query>' '<variables-json>'
```

Destructive ops (`railway down`, `railway delete`) are blocked at the
settings layer.

### Real Sports

Session state lives in `scraper/storage_state.json` (gitignored), seeded on
Railway via `REALSPORTS_STORAGE_STATE_B64GZ` (gzip+base64 of that file, set
on cron-job1 and cron-dayclose). Sessions die server-side after roughly three
weeks; the symptom is 401s from every `web.realapp.com` endpoint while the
web app still renders (it falls back to guest).

Re-login gotcha (2026-07-02): `POST /login` returns 403
"Please refresh the page and try again" for plain scripted Chromium --
including this repo's own `scripts/realsports_login.py` -- regardless of UA
or automation-flag masking. The Playwright MCP browser passes the check. To
re-seed: log in via Playwright MCP, dump localStorage into Playwright
storage-state format (cookies are empty; auth is all localStorage), write
`scraper/storage_state.json`, then upsert the b64gz onto cron-job1 and
cron-dayclose and redeploy both.

Railway IDs:
- Project: `ab83f44c-0bbc-4a58-931c-37d9fbfda73a`
- Production env: `d57a759e-e189-439b-a612-bd220ef59c39`
- Services: cron-job1 `2e110589-9527-4541-a754-41c4719515ba`, cron-job1-late `2b0cd5aa-8793-45a5-bca0-e81c6d8455ff`, cron-job2 `4a511ed2-10ad-441f-bf9a-3748c1e6b929`, cron-dayclose `606d950d-7d7d-4f5a-a049-b9fa69799169`,
  postgres `5e827da3-6df6-4349-97ad-a800ece2716d`, redis `bb131bec-4edd-4809-accd-e09e09aacbf6`, api `f4750eda-fd6c-432b-b6f5-34254013c271`, frontend `d56dccf4-85b3-4ba0-acaf-58ef0cced58c`
- Cron schedules (UTC): cron-job1 `0 13 * * *`, cron-job1-late `*/30 16-23 * * *`
  (start command `oracle-cron --job job1late`), cron-job2 `*/5 14-23,0-3 * * *`,
  cron-dayclose `0 6 * * *`

To redeploy a service:
```bash
scripts/rwgql.sh 'mutation { serviceInstanceDeployV2(serviceId: "SERVICE_ID", environmentId: "d57a759e-e189-439b-a612-bd220ef59c39") }'
```

### Local dev setup

Verify credentials are working before starting work:

```bash
bash scripts/dev.sh
```

This checks GitHub, Railway (both auth paths), Odds API, and Real Sports
credential presence. It reads credentials from `.claude/settings.local.json`
and validates they work.

### Scheduled routines (cloud)

Two routines run daily in Anthropic's cloud (manage at
https://claude.ai/code/routines; push notifications enabled on both):

- **WNBA pre-freeze guard** (`trig_01FzJJAJ89ggeMgkgoPRTEzg`, 13:30 UTC,
  30 min after cron-job1): verifies tonight's picks will freeze -- pool,
  freeze machinery, model SHA, frontend regression. Self-heals redeploys and
  documented values; escalates concisely to the rolling issue labeled
  `ops-guard`; silent when healthy.
- **WNBA dayclose verify** (`trig_015HXQzUQjAgVFwfv6b7q8y6`, 07:00 UTC,
  1h after cron-dayclose): verifies corpus ingest, watches for the Real
  Sports session-death signature six hours before job1, posts a results
  digest to the issue labeled `ops-results` (the ledger that replaced
  RESULTS.md).

Routine design rules (violating these caused the June outage response to
fail): HTTP-only checks (api endpoints + Railway GraphQL logs; the cloud
container cannot reach Postgres), credential gate first, never scripted
Real Sports login, never commit to main, never append to STATUS.md,
expected values (model SHA, schedules) read from this file at runtime.
The legacy routines (14:00 UTC readiness check, 12:00 UTC improvement
agent) are disabled, not deleted.

### Constraints

- Never echo a credential value into a log, commit, chat message, comment,
  or PR body. Reference by env var name only.
- Do not store config in local files. Config lives on Railway only.
- Never create new accounts or generate new long-lived credentials.
  If a credential is missing or expired, escalate on the `ops-guard` issue.
