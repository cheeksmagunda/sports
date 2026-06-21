# CLAUDE.md (WNBA Oracle build)

This is an unattended build. Follow Part 0 of the handoff document.

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
both`. See STATUS.md and DECISIONS.md for full roadmap and reverse paths.

## Autonomy

- Never stop to ask the human a question. Use the Part 0.1 protocol.
- Dependencies: you are pre-authorized to add any dependency that is a
  well-known PyPI or npm package, permissively licensed (MIT, BSD, Apache),
  and needed for a capability listed in the handoff. Log each one in
  DECISIONS.md. Do not pause to confirm.
- When the handoff says "research" or "open question," decide and log.
  Never interpret it as "ask."

## Work hygiene

- Read files before editing. Preserve existing style.
- Commit after every working increment with a descriptive message.
- Keep code grep-able and consistent. Remove dead code and scratch files.
- Maintain README.md, DECISIONS.md, NEEDS_HUMAN.md, STATUS.md as you go.
  These are required deliverables for this project.

## Output style

- No em dashes. Vary sentence length. No emojis.
- Distinguish verified facts from synthesized reasoning in DECISIONS.md.

## Credentials and authorization

All credentials are pre-injected into the session environment via
`.claude/settings.local.json` (gitignored, machine-local). You do NOT need to
source `.env` before using them -- `GITHUB_TOKEN`, `RAILWAY_TOKEN`,
`DATABASE_URL`, and `REDIS_URL` are already exported when any tool runs.

The owner has granted blanket authorization to use these credentials for any
operation this project legitimately requires. Do not pause to re-confirm.

### GitHub / git

The repo's git credential helper reads `$GITHUB_TOKEN` directly. Plain
`git push origin main` works without any prefix. For `gh` CLI operations use
`GH_TOKEN="$GITHUB_TOKEN" gh ...`.

### Railway

`RAILWAY_TOKEN` is a workspace token. The Railway CLI rejects workspace tokens --
never use `railway link`, `railway up`, or any Railway CLI mutation command.

Use `scripts/rwgql.sh` for all Railway GraphQL operations:

```bash
scripts/rwgql.sh '<graphql query>'
scripts/rwgql.sh '<graphql query>' '<variables-json>'
```

The script handles auth automatically. Destructive ops (`railway down`,
`railway delete`) are blocked at the settings layer.

Railway IDs:
- Project: `ab83f44c-0bbc-4a58-931c-37d9fbfda73a`
- Production env: `d57a759e-e189-439b-a612-bd220ef59c39`
- Services: cron-job1 `2e110589`, cron-job2 `4a511ed2`, cron-dayclose `606d950d`,
  postgres `5e827da3`, redis `bb131bec`, api `f4750eda`, frontend `d56dccf4`

To redeploy a service:
```bash
scripts/rwgql.sh 'mutation { serviceInstanceDeployV2(serviceId: "SERVICE_ID", environmentId: "d57a759e-e189-439b-a612-bd220ef59c39") }'
```

### Other credentials

- `ODDS_API_KEY`: authorized for any The Odds API request.
- `REAL_SPORTS_USERNAME` / `REAL_SPORTS_PASSWORD`: authorized for headless
  Real Sports login (Job 1 re-auth flow, Part 0.6 of handoff). Source `.env`
  for these two since they are not in `settings.local.json`.
- `DATABASE_URL` / `REDIS_URL`: authorized for any read or write the project
  legitimately requires. These connect to Railway internal endpoints and only
  work from within Railway containers; for local use see `DATABASE_PUBLIC_URL`
  in `.env`.

### Constraints

- Never echo a credential value into a log, commit, chat message, comment,
  PR body, or `DECISIONS.md`. Reference by env var name only.
- The `Read(./.env)` deny rule blocks the Read tool from opening `.env`.
  Source through shell if you need values not already in the environment:
  `set -a && source .env && set +a && <command>`.
- Never create new accounts or generate new long-lived credentials.
  If a credential is missing or expired, log to `NEEDS_HUMAN.md`.
