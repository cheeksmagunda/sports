# Status

Last verified: 2026-09-27 (Codespace `fluffy-zebra-g4gqq746477q2jg` /
`scripts/codespace-railway-env`, issue #504 / PR #489)

This file records application state only.

## Application state

- Package: `nba-oracle` workspace member
- Scope live now: health-only FastAPI (`GET /health`) + NBA calendar /
  coverage vocabulary + auth-blocked `nba-corpus-g-backfill` gate
- Deploy surface: `nba-oracle/Dockerfile` + `nba-oracle/railway.toml`
  (DOCKERFILE builder; health-only image lineage from #486; no Playwright in
  the serving image)
- Calendar: `NEXT_REGULAR_SEASON_OPEN = 2026-10-20`; tracked seasons
  `2002`..(current Eastern season label) for Corpus G planning
- Ingest: `nba-corpus-g-backfill` gate writes a blocked coverage matrix and exits
  non-zero without portfolio `REALSPORTS_*`; HTTP Corpus G client not wired yet.
  Separate observation-only path: `nba-history-load` loads public `data.nba.com`
  schedule/gamedetail into Postgres over public TCP (`sslmode=require`), no Real
  Sports auth.
- Public history tables (target): `nba_history_games`, `nba_history_player_games`,
  `nba_history_season_coverage`. Verified counts: pending load this session.
- Not started: schemas, modeling, scheduling, contest logic, nightly worker

## Railway mono (`sports-oracle` / `nba-staging`, env `7ac1e6f8-…`)

Verified 2026-09-27 from Codespace. Non-serving scaffold only (#457 / #504).

| Service | Source | Last observed | Notes |
| --- | --- | --- | --- |
| `nba-api` | `cheeksmagunda/sports` (connected) | Online | Deployment id `c35dd53b-…` Online (post-queue). No public domain. External `/health` therefore unverified from outside Railway. |
| `nba-worker` | not shown / Failed | Failed | Leave disconnected until Real Sports auth + nightly are authorized. |
| `nba-frontend` | not shown / Failed | Failed | No frontend package; leave disconnected. |
| `nfl-frontend` | Offline | Offline | Stray service instance visible in `nba-staging`; not an NBA serving path. |
| `Postgres-6eeu` | n/a | Online | Volume `postgres-volume-jmAe`. Public TCP proxy ACTIVE (`trolley.proxy.rlwy.net`). `DATABASE_PUBLIC_URL` set with `sslmode=require`. Public history load counts: pending verify. |

No public NBA domain. No contest features. No Real Sports credential verified on NBA services. Serving is not dual-firing for NBA: only `nba-api` is Online (queued rebuild); worker/frontend Failed/Offline.

## Boundaries

- NBA domain behavior stays in `nba-oracle`
- Shared technical abstractions may move to `oracle-core` only after proven
  provider-neutral use across multiple sports
- No contest entry code in this package
