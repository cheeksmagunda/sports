# Morning brief — nfl-oracle overnight (2026-09-06)

**For:** operator (Ben)  
**Timezone:** America/Chicago (CT)  
**Quiet overnight:** yes — local-only work; **no push**  
**As of:** ~02:30 CT (2026-09-06)

---

## HEAD / branch

| Item | Value |
|------|--------|
| Repo | `/workspace/sports` |
| Branch | `codex/nfl-data-schemas-scaffold` |
| HEAD | `5b013f1` |
| Ahead of | `origin/main` (29 local commits) |
| Working tree | clean after overnight commits |
| Pytest | **172 passed** (was 168 at `8e3c9c6`; +4 harden) |
| Push | **none** — Contents:Write 403 on box PAT |

Committed: `5b013f1` — **172 tests**. Still **no push**.

---

## Features built overnight (through this turn)

### This turn (~02:30 CT) — contest dry-run × week/slate harden
1. `resolve_dry_run_schedule_slate` — attach priority:
   - explicit `schedule_date`
   - explicit `schedule_week` (+ decision season)
   - label `event_time` → date resolve (fixtures: 2025-09-07 → week 1)
   - else week-1 fallback (documented in `dry_run_attach.source`)
2. Optional `schedule_team` on CLI + `GET /research/shadow/contest-dry-run`
3. `dry_run_attach` meta on attached slate; CLI `--text` prints slate summary
4. Tests (+4 → **172**); gates untouched (`contest_entry=false`; submit hard-deny)

### Prior overnight (through `8e3c9c6`)
| Commit | Feature |
|--------|---------|
| `8e3c9c6` | Week/slate resolution (`calendar.slate`) + research route + optional dry-run attach (168) |
| `3ca5953` | Offline walk-forward eval report vs `feature_ridge` (160) |
| `6cf37c9` | Offline contest dry-run five-card shadow slate (155) |
| `2e1a214` | OpenAPI research tags + readiness-score endpoint |
| `999792a` | Wire `feature_ridge` into shadow routes behind flag |

Also on branch (scaffolds): Corpus G ingest boundary, value labels/baselines,
feature registry (incl. offline stubs), identity density/aliases/dedup,
schedule census (24 seasons / 6499 games), provider stubs (#91), research
service (shadow preview/rank, gates, coverage, schedule summary), strategy
algebra + entry gates (always deny).

---

## Hard gates (unchanged — do not flip)

- `contest_entry=false` everywhere
- `FiveCardProviderStub.submit` hard-denies
- `evaluate_entry_gates` → `package_submit_hard_deny` ok=false
- No Railway deploy source / no in-repo `railway.toml` for nfl-oracle
- No secrets committed

---

## Blockers (do **not** retry from box)

| Blocker | Why | Exact unblock |
|---------|-----|----------------|
| **GitHub Contents:Write 403** | Fine-grained PAT lacks Contents write | Grant Contents:Write on PAT **or** push from Codespace / machine with write token (see commands below) |
| **Real Sports auth missing** | No storage_state / B64GZ on box | Seed ignored `nfl-oracle/scraper/storage_state.json` (0600) **or** Codespaces secret / `REALSPORTS_STORAGE_STATE_*` (never commit) |
| **Codespace SSH from box** | SSH hangs / dead | Use Codespace UI terminal; do not rely on box→CS SSH |
| **#91 live five-card contract** | Still stub / unverified | Operator live capture when auth present — out of overnight scope |
| **Railway token scope** | CS `railway whoami` Unauthorized with current token | Ben refreshes Railway token with project access; `gh secret set RAILWAY_TOKEN --app codespaces` |

---

## Exact unblock commands (operator)

### A) Publish branch (preferred: Codespace UI, not box)

```bash
cd /workspaces/sports   # or Mac worktree with write token
git fetch origin
# Option 1: cherry / merge local branch if already present; else receive bundle
# Bundle path previously staged: /tmp/nfl-schemas.bundle + /tmp/cs-push-bundle.sh
git checkout -B codex/nfl-data-schemas-scaffold
git log -1 --oneline   # expect harden commit / 8e3c9c6 ancestor
git push -u origin HEAD
gh pr create --draft --base main --title "nfl-oracle: schemas + research + dry-run (#89)" \
  --body "Tracking #89 / #94. Observation only; no contest entry."
# Comment on #94 with PR URL
```

From box only after Contents:Write is granted:

```bash
cd /workspace/sports
git push -u origin HEAD   # currently 403 — do not retry until token fixed
```

### B) Seed Real Sports auth (box or Codespace)

```bash
# Never print storage_state / tokens
mkdir -p nfl-oracle/scraper
# place storage_state.json mode 0600, OR:
# gh secret set REALSPORTS_STORAGE_STATE_B64GZ --app codespaces --repo cheeksmagunda/sports <…>
scripts/auth-check nfl-oracle --offline
make -C nfl-oracle provider-status
```

### C) Offline smoke (no auth required)

```bash
cd /workspace/sports
uv run --package nfl-oracle pytest nfl-oracle/tests -q
make -C nfl-oracle research-smoke
make -C nfl-oracle contest-dry-run
# with schedule attach:
uv run --package nfl-oracle nfl-contest-dry-run --include-schedule-slate --text \
  --project-root nfl-oracle/tests/fixtures/offline_research
```

### D) Research slate / dry-run HTTP (local)

```bash
make -C nfl-oracle research-serve   # needs serve extra / uvicorn
# GET /research/schedule/slate?season=2025&week=1
# GET /research/shadow/contest-dry-run?include_schedule_slate=true
```

---

## Safe next (after unblock)

1. Push draft PR → link #89 / #94  
2. Seed Real Sports auth → denser Corpus G beyond catalog seeds  
3. #91 live provider contract capture (still deny submit until verified)  
4. Optional: Railway staging link only after token refresh (no production secrets from overnight)

---

## Docs

| File | Role |
|------|------|
| `/workspace/codex-nfl/HANDOFF.md` | Overnight handoff |
| `/workspace/codex-nfl/EXECUTOR_HANDOFF.md` | Short executor pointer |
| `/workspace/sports/nfl-oracle/STATUS.md` | Application state of record |

**Policy:** quiet overnight continues — **no push** from box until Contents write is fixed.
