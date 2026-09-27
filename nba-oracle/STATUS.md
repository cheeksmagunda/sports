# Status

Last verified: 2026-09-27T03:25:00Z (nba-staging health + service matrix; #453 / #523)

## Product goal lock (#453 / #523)

Portfolio goal: root `../README.md` (Product goal) - 5 players / day maximizing
Real Sports Highest value boards. NBA has no contest serve path yet; when
modeling starts, own-model surface is valuelaw/ridge/EB-shaped (no LightGBM;
#523). History ingest open on PR #489 (diverged from `main`; check mergeable
at land time).

## Railway mono (`sports-oracle` / `nba-staging`)  -  2026-09-27T03:25Z

Verified via Codespace `fluffy-zebra-g4gqq746477q2jg` /
`scripts/codespace-railway-env`. Non-serving scaffold only. No contest
features. No Real Sports credential on NBA services.

| Service | Status | Notes |
| --- | --- | --- |
| `nba-api` | Online | Public `https://nba-api-nba-staging.up.railway.app/health` → `{"status":"ok","version":"0.1.0"}` |
| `nba-worker` | Failed | No worker role yet |
| `nba-frontend` | Failed | No frontend package yet |
| `Postgres-6eeu` | Online | Volume ~0.1 / 4.9 GB; **empty app schema** (unused by health scaffold) |

Earlier 2026-09-27 pause left services disconnected after Railpack failures;
Dockerfile + `railway.toml` are on `main` (#486). Health domain present and
responding at verify time.

## Application state

- Package: `nba-oracle` workspace member
- Scope live now: contract-compliant scaffold + health-only FastAPI (`GET /health`)
- Deploy surface: `nba-oracle/Dockerfile` + `nba-oracle/railway.toml` (DOCKERFILE builder)
- Wired for root checks: test, lint, typecheck, build, boundary, and app contract
- CI: root `make test-nba` runs in `backend-ci.yml` alongside WNBA/NFL/NHL import smoke
- Calendar / TRACKED seasons: not started (NBA.com lists 2026-10-20 regular-season open; not recorded in-app)
- Not started: provider ingest on `main`, schemas, modeling, scheduling, contest logic
- Open: multi-year public history loader + calendar honesty on PR #489

## Boundaries

- NBA domain behavior stays in `nba-oracle`
- Shared technical abstractions may move to `oracle-core` only after proven
  provider-neutral use across multiple sports
- No contest entry code in this package
