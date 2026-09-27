# Claude task (Grok Bot delegated): NFL model win-capability backtest (#280)

You are Claude Code in `/Users/hanslarson/Developer/sports`. Grok Bot is PM. Do the coding. Do not wait for more chat.

## Goal
Close the gap documented in GitHub issue #280: production model's win-capability has never been backtested against hindsight-best on real Corpus G. Naive baseline captures ~65% mean; human winners in zero-boost regime ~97.5%.

## Constraints
- Issue-first: all commits/PR reference #280.
- Prefer Codespace `fluffy-zebra-g4gqq746477q2jg` for write-path / Railway. Local Mac OK for offline corpus replay if data exists under nfl-oracle.
- Do NOT touch branches/worktrees: `fix/299-nhl-week2-live-audit`, `/tmp/sports-railway-auth`, `fix/306-*`, `fix/279-*`.
- Use a fresh branch from updated main, e.g. `fix/280-production-model-backtest`, ideally in a separate git worktree.
- No contest entry. No Unicode em dash (U+2014).
- No LightGBM / third-party ML beyond existing app/connectors (operator v2 constraint). Use existing production path (`fit_model` / predict / optimize) and replay harness.
- Never print secrets.

## Acceptance
1. Wire a real-archive backtest of the **production** model path (not only the naive EWMA baseline) against Corpus G / documented corpus, reporting capture ratio vs hindsight-best (mean/median/min/max, n games).
2. Compare to naive baseline and to STATUS field-winner benchmarks where apples-to-apples.
3. Land results in `nfl-oracle/STATUS.md` from the live run (numbers you actually measured).
4. Tests for the new harness entrypoint; `make test-app APP=nfl-oracle` (or focused suite) green.
5. PR linked to #280; `make write-path-check` before push; squash-merge when required checks green if in scope.

## First steps
1. `gh issue view 280` and read `nfl-oracle/STATUS.md` production backtest section + `nfl_oracle.replay` modules.
2. Create worktree/branch. Implement. Run. Document. PR.

Start now. Report PR URL when open.
