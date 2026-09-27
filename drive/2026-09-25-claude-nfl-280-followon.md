# Claude brief: NFL #280 follow-on (player selection / Corpus C)

Operator (2026-09-25 AM CT): Claude CLI is back. Grok is PM; you implement on Codespace or a Mac worktree. Squash-merge when checks green. No em dash (U+2014).

## Already done (do not redo)
- Production backtest harness on main via PR #293 (`nfl_oracle.replay.production_backtest`).
- Mean capture ~67.9% vs naive ~65.6%; far below field 97.5% zero-boost (different denominator).
- Issue #280 stays OPEN on purpose (`Refs`, not `Closes`).

## Your job
Close the capability gap called out on #280: **player selection**, not the optimizer.

Acceptance (pick a scoped first PR that moves the issue; open sub-issues if needed):
1. Corpus C contest-pool replay: same visible pool the field saw, report capture / top-N vs field winners for apples-to-apples comparison.
2. Or: projection calibration by position + availability diagnostics feeding that harness.
3. Unit tests; update `nfl-oracle/STATUS.md` with numbers; PR body `Refs #280` (or `Closes #280` only if the gap is actually answered).

## Constraints
- No LightGBM / third-party ML beyond existing APIs.
- Do not flip production objective to P(win) without evidence.
- Do not touch WNBA #317 (GHA benchmark already running), Railway auth, or NHL WIP.
- Prefer fresh worktree off `origin/main`. Avoid dirty Claude trees that would regress STATUS/FILES.
- Codespace canonical: `fluffy-zebra-g4gqq746477q2jg`. `make write-path-check` before push.

## Start
Read issue #280 comments, `nfl-oracle/STATUS.md`, `nfl_oracle/replay/production_backtest.py`, then ship the smallest PR that lands Corpus C contest-pool comparison or the calibration cut behind it.
