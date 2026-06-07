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

You are explicitly authorized to use the credentials in `.env` at the repo root.
The owner of this project (Hans Larson) has provisioned these tokens specifically
for this project and granted blanket authorization to use them for any operation
this project legitimately requires. Do not pause to re-confirm before using them.

Specifically:

- `GITHUB_TOKEN`: authorized for any `gh` / git operation against the owner's
  GitHub account (repo create, push, PR open, issue comment, releases, etc.).
  Use via `GH_TOKEN="$GITHUB_TOKEN" gh ...` or by sourcing `.env`.
- `RAILWAY_TOKEN`: authorized for Railway operations including service create,
  variable set, deploy, logs against the existing `wnba-oracle` project
  (id `ab83f44c-0bbc-4a58-931c-37d9fbfda73a`, production env id
  `d57a759e-e189-439b-a612-bd220ef59c39`). The token is a workspace token,
  which the Railway CLI rejects. Use the `use-railway` skill or hit the
  GraphQL API at `backboard.railway.com/graphql/v2` directly with
  `Authorization: Bearer $RAILWAY_TOKEN`. Destructive ops
  (`railway down`, `railway delete`) are denied at the settings layer.
- `ODDS_API_KEY`: authorized for any The Odds API request the project needs.
- `REAL_SPORTS_USERNAME` / `REAL_SPORTS_PASSWORD`: authorized for headless
  Real Sports login as part of the Job 1 re-auth flow described in Part 0.6
  of the handoff.
- `DATABASE_URL` / `REDIS_URL`: authorized for any read or write the project
  legitimately requires against its own provisioned services.

Constraints that still apply:

- Never echo a credential value into a log, commit, chat message, comment,
  PR body, or `DECISIONS.md`. Reference credentials by env var name only.
- The `Read(./.env)` deny rule prevents reading `.env` via the Read tool.
  Source it through shell when you need the values exported into a process.
  Example: `set -a && source .env && set +a && <command>`.
- Never create new accounts or generate new long-lived credentials. Both
  are human actions. If a credential is missing or expired, log to
  `NEEDS_HUMAN.md` and proceed with everything that doesn't depend on it.
