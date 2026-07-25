---
name: reseed-realsports
description: Recover a dead Real Sports session - Playwright MCP login, rebuild storage_state.json, re-seed Railway crons. Use when web.realapp.com returns 401s everywhere or the pool comes back empty.
disable-model-invocation: true
---

# Re-seed the Real Sports session

Sessions die server-side after roughly three weeks. Symptom: 401 from every
`web.realapp.com` endpoint while the web app still renders (guest fallback).

**Never attempt a scripted or headless login.**
`POST /login` bot-blocks plain scripted Chromium with a 403 regardless of UA
masking. Only the Playwright MCP browser passes the check (verified
2026-07-02).

## Procedure

1. Open the Playwright MCP browser at https://web.realapp.com and log in
   with `$REAL_SPORTS_USERNAME` / `$REAL_SPORTS_PASSWORD` (in the session
   env). Never echo the values.
2. Confirm login worked: an authed endpoint (e.g. the contests list) returns
   200, not 401.
3. Dump localStorage from the page and convert it into Playwright
   storage-state format. Cookies are empty; the auth lives entirely in
   localStorage. Write the result to `scraper/storage_state.json`
   (gitignored).
4. Encode it: `gzip -c scraper/storage_state.json | base64` (single line).
5. Upsert that value as `REALSPORTS_STORAGE_STATE_B64GZ` on BOTH cron-job1
   (`2e110589-9527-4541-a754-41c4719515ba`) and cron-dayclose
   (`606d950d-7d7d-4f5a-a049-b9fa69799169`) via `scripts/rwgql.sh`, then
   redeploy both services (see the `/redeploy` skill).
6. Verify: trigger or await the next job1 run and confirm the pool is
   non-empty (`job1_enrichment` rows for today, or api `/slate/{date}`).

Environment: production env id `d57a759e-e189-439b-a612-bd220ef59c39`.
