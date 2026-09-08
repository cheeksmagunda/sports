# NFL close-out handoff (Parts A-E)

Status: done
Created: 2026-09-08
Owner: Claude session sports-closeout-parts-a-e-b75cbf, for Johannes

Written for someone who has not read tonight's work. Part 1 (earlier tonight,
issues #94/#99/#101/#103/#105, PRs #100/#102/#104/#106) is not repeated here.

## Merged tonight

- **[#107](https://github.com/cheeksmagunda/sports/pull/107)** - nfl-oracle:
  research API, ~6500-game schedule census, identity and feature registry,
  leakage-safe `feature_ridge` value model behind a flag, offline contest
  dry-run, walk-forward evaluation. Rebased from the preserved overnight
  branch (30 commits), two subject lines reworded to carry `(#89)` (no code
  changed - verified by an empty `git diff` against the original branch
  before rebasing), plus two follow-up commits: a lint/format fix (the real
  cause of the red `test-and-quality`/`devcontainer-smoke` jobs - see below)
  and a CI fix that added the missing `Test NFL backend` step.
- **[#93](https://github.com/cheeksmagunda/sports/pull/93)** - python
  minor/patch group: fastapi, pydantic, sqlalchemy, pytest, ruff, playwright.
  Needed one follow-up commit (see below) because the ruff bump inside this
  same PR surfaced 5 new lint findings on unrelated scripts.
- **[#6](https://github.com/cheeksmagunda/sports/pull/6)** - types-pyyaml
  patch bump.
- **[#108](https://github.com/cheeksmagunda/sports/pull/108)** - frontend
  minor/patch group: react, react-dom, their type stubs, react-router-dom,
  `@playwright/test`, globals, typescript-eslint. This PR did not exist when
  the task started; dependabot closed the original #96 mid-session and
  opened #108 in its place (one more package needed updating in the group).
  Not something I closed - confirmed via the API and via dependabot's own
  standard supersede pattern (same as #4 -> #9).

Main is green after all four merges: `backend-ci` on the current HEAD
(`cecb527`) is `success`.

## A6 safety review - gate by gate, quoted from the merged diff

All five gates from the morning brief are closed. Nothing tonight opened or
weakened any of them.

1. **`contest_entry` is false everywhere.** Every constructor, dict literal,
   and schema field defaults to `False`; `strategy/schema.py` types it
   `Literal[False]` with a validator that raises if it is ever `True`.
2. **`FiveCardProviderStub.submit` still hard-denies:**
   `raise ProviderNotReady("contest_entry_forbidden_by_nfl_oracle_policy")`.
3. **`evaluate_entry_gates` still returns `package_submit_hard_deny` with
   `ok=False`**, and `EntryGateReport.contest_entry` is hardcoded `False` in
   the return, independent of every other gate's state.
4. **No `railway.toml` for nfl-oracle, no deploy source added.** Only
   `nfl-oracle/Dockerfile` and `nfl-oracle/docker-compose.yml` exist, both
   explicitly local-observation-only ("Not Railway. Do not deploy to
   production."), no `RAILWAY_TOKEN` references.
5. **No secrets, tokens, or `storage_state` files committed.**
   `git diff --name-only origin/main...HEAD` (121 files) contained none.

Full evidence with code excerpts is in the #107 PR body.

## What A5 actually found (nobody had read the failures before tonight)

Three real, narrow issues, all fixed without touching any test assertion,
lint rule, or hard gate:

- `nfl-oracle/src/nfl_oracle/strategy/__init__.py` had one ruff `I001`
  unsorted-import error.
- Because `make lint` stops at the first ruff failure, `ruff format --check`
  had never run against 4 files in this branch. They needed reformatting
  (whitespace/line-wrap only, no logic change).
- `test_local_research_compose_no_secrets` (a real safety test - it wants no
  `env_file` and no `storage_state` reference in `docker-compose.yml`) was
  failing because the compose file's own comments *described* their absence
  using those literal words. Reworded the comments; the test and its
  assertions are untouched.
- Separately, `test-and-quality` never actually ran nfl-oracle's pytest
  suite (only `make test-wnba`, not `make test-nfl`). Added the missing
  `Test NFL backend` step so the 174 nfl-oracle tests, including the one
  that needs a live Docker daemon, run in CI on every future PR. Confirmed
  in the merged run: `Test NFL backend: success`.
- On #93, the ruff 0.15.14 -> 0.16.6 bump in that same PR surfaced 5 new
  findings on unrelated portfolio scripts under ruff's newer defaults (2x
  I001, 2x EXE001 shebang-not-executable, 1x BLE001 on a deliberately blind
  `except Exception` that exists so driver errors, which can contain
  passwords or connection URLs, never reach stdout). Fixed with auto-fix,
  `chmod +x`, and one scoped `noqa: BLE001` with the existing justification
  comment - no rule relaxed globally.

## Still open, and why

- **[#15](https://github.com/cheeksmagunda/sports/pull/15) typescript 5.9->7.0,
  [#14](https://github.com/cheeksmagunda/sports/pull/14) vite 7.3->8.2,
  [#13](https://github.com/cheeksmagunda/sports/pull/13) @eslint/js 9->10,
  [#12](https://github.com/cheeksmagunda/sports/pull/12) @vitejs/plugin-react
  4.7->6.0, [#8](https://github.com/cheeksmagunda/sports/pull/8) mypy
  1.20->2.3, [#9](https://github.com/cheeksmagunda/sports/pull/9) pyarrow
  21->25** - major bumps, held for deliberate review, exactly as directed.
  Each has a comment stating it's held.
- **[#48](https://github.com/cheeksmagunda/sports/pull/48) actions group** -
  held even though it was on the "merge" list. Checked the actual version
  deltas: actions/checkout 5.1.0->7.0.1, setup-go 6.5.0->7.0.0, setup-node
  4.4.0->7.0.0, upload-artifact 4.6.2->7.0.1, download-artifact 5.0.0->8.0.1
  are all major bumps. The repo's `dependabot.yml` groups all
  `github-actions` updates under one `actions` group with no
  minor/patch restriction (unlike the `uv` and `npm` groups), so it
  legitimately bundles majors. The standing rule against merging majors the
  night before a live slate wins over the more specific instruction to
  merge this one; commented with the reasoning on the PR.
- **[#7](https://github.com/cheeksmagunda/sports/pull/7) structlog
  25.5.0->26.1.0** - same situation. structlog uses calendar versioning, so
  this is likely a routine annual release, but the version number crosses a
  major component, which is exactly why dependabot filed it standalone
  instead of folding it into the python-minor-and-patch group. Held, with a
  comment explaining the deviation.
- **[#41](https://github.com/cheeksmagunda/sports/issues/41)** (starlette/
  pyarrow CVE patch) is gated behind the held pyarrow major in #9 and could
  not be closed tonight.
- **[#29](https://github.com/cheeksmagunda/sports/pull/29),
  [#28](https://github.com/cheeksmagunda/sports/pull/28),
  [#25](https://github.com/cheeksmagunda/sports/pull/25)** - left untouched;
  other agents' work in progress.
- **[codex/nfl-data-schemas-scaffold](https://github.com/cheeksmagunda/sports/tree/codex/nfl-data-schemas-scaffold)**
  is permanent and must never be deleted or force-pushed. It is the
  preservation record for the 30 overnight commits, independent of #107
  having merged.

## Part C - Grok Bot

Corrected its stale state: the 5 commits it believed were unpushed on
`chat/89-nfl-real-corpus` are ancestors of `origin/main` (`git merge-base
--is-ancestor` returns true; `git log origin/main..origin/chat/89-nfl-real-corpus`
is empty), verified independently, twice, before and after tonight's
merges. It acknowledged, abandoned its stalled push, and was told to do no
further work tonight. Its saved instructions (previously a long, informal,
"assume executive authority" / "root administrator" document with a garbled
operator name) were replaced with the exact seven-point instruction block
from tonight's task. It read the new instructions back verbatim, confirming
the update took. No task was assigned to it.

## Part D - Mac

- `git worktree prune` cleared the dead `/private/tmp/sports-nfl-oracle-89`
  entry from `~/Developer/sports`.
- Two `.claude/worktrees/` entries remain by design, not deleted:
  `hungry-hopper-c53d3c` (branch `CLAUDE/sports-closeout-johannes-97ddb4`,
  at `28acf1c` - the peer session that appears to be tonight's completed
  Part 1) and `nfl-research-consolidation-6adc36` (detached HEAD at
  `4775951`, with one pre-existing uncommitted modification that is not
  mine to touch).
- `~/Developer/sports` is on current `main` (`cecb527`), clean except one
  untracked `.codex-current-screen.png` left by another tool - not part of
  this task, not removed. `make write-path-check` (run with `GITHUB_TOKEN`
  unset) passes: push allowed, 0 unpushed commits.
- `~/Developer/nfl-rescue/` and its bundle are untouched.

## Wednesday readiness

**On main now:** the full nfl-oracle research/observation stack - research
API, schedule census, identity and feature registry, `feature_ridge` value
model (behind a flag, leakage-safe/walk-forward only), offline contest
dry-run, walk-forward evaluation report. All of it is observation-only.

**What still has to happen before this could be used against a live slate**
(unchanged from the morning brief, none of it done tonight):

1. **Real Sports auth is not seeded.** Needs `storage_state.json` at mode
   `0600` under `nfl-oracle/scraper/`, or a Codespaces secret
   (`REALSPORTS_STORAGE_STATE_B64GZ`). This is an operator action; nothing
   should ever commit this file or its value.
2. **The Railway token is `Unauthorized` from the Codespace.** Needs
   refreshing with project access before any Railway-side step (staging or
   otherwise) can run. Note nfl-oracle itself still has no `railway.toml` or
   deploy source at all - there is no nfl-oracle deployment path to point a
   working token at yet.
3. **Issue [#91](https://github.com/cheeksmagunda/sports/issues/91)'s live
   five-card contract is still unverified against a real contest.** The
   provider stub's `readiness()` reports `UNVERIFIED` until that capture
   happens with real auth present.
4. **Contest entry remains hard-denied in code, and nothing tonight changed
   that.** `contest_entry` cannot become `True` through any path merged
   tonight; `FiveCardProviderStub.submit` and `evaluate_entry_gates` both
   still hard-deny unconditionally, verified above and in #107's diff.
