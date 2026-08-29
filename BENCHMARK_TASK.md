# Model Research Benchmark Workflow - Continuation Task

## Status Summary
**Location**: `main` (PR #26 merged, PR #33 merged 2026-08-28)
**Last Updated**: 2026-08-29 — sweep still has not completed; do not treat this as stale

The one real dispatch so far (2026-08-28, `workflow_dispatch` run 33147365291,
20 shards) was cancelled by @cheeksmagunda about 2 minutes in — only shards 10
and 12 finished naturally, no merge ran. PR #33 (merged the same morning)
explains why cancelling was correct: the benchmark was structurally pinned to
a broken game-identity fallback (empty `game_id` on every sample forced the
reciprocal team/opponent path, which self-contradicted on 14/82 identity
days) and accepted only 35/100 slates. The fix plus a new
`--report-coverage`/`--min-eligible-slates` preflight gate recovers coverage
to 78/100. **No sweep has run against the fixed code yet.**

See `wnba-oracle/MODEL_PICK_POSTMORTEM_2026-08-28.md` (once written) for the
real-money motivation: a live "Draft"-format entry built from the system's
2026-08-28 picks scored 29.92, placing 6384th of 6800. If that postmortem
implicates `starter_unknown_fade` (relaxed 1.0 → 0.75 in #24) or the
leverage/ceiling weighting, this benchmark sweep is the evidence-gated way to
validate any proposed revert — do not ship a knob change off one slate's
result alone.

## What Was Completed
- ✅ Benchmark script implemented, sharded across 20 parallel workflow jobs
  (not 16 — correcting this doc's original estimate) at 3500 samples/variant
- ✅ Script follows existing conventions (env config, read-only DB access, atomic output writes)
- ✅ PR #33: fixed game-identity resolution + added a coverage preflight gate
  before the shard fan-out (35/100 → 78/100 eligible slates)

## Remaining Work (In Priority Order)

### Phase 1: Execute & Complete Benchmark Runs
1. **Dispatch workflow runs**
   - Trigger the 20-shard benchmark workflow (`.github/workflows/model-research-benchmark.yml`,
     `workflow_dispatch`) now that PR #33's coverage fix is in — the 2026-08-28
     run predates the fix and should not be treated as a real result
   - Monitor shard execution status (budget ~4.3h/shard, ~86 CPU-hours total)
   - Verify all shards complete successfully

2. **Merge shard results**
   - Consolidate results from 16 shards
   - Ensure no data loss or corruption in merge
   - Validate merged dataset integrity

3. **Analyze variant outcomes**
   - Compare baseline vs. knob-based variants (same-game/same-team boosts, dynamic team cap, duplication-aware payout, leverage/ceiling weights)
   - Compare temperature variants (0.7–1.5 sigma scaling range)
   - Metrics: realized placement, gap-to-winner, beat-median rate, payout capture under top-20 curve
   - Generate MODEL_RESEARCH_BENCHMARK.md summary

### Phase 2: Follow-Up Work (After Analysis)
- **Evidence-gated single-knob promotion**: Use benchmark results to decide which knob variants merit promotion to shadow pipeline
- **Contest-placement probability modeling**: Build model from realized placement data
- **Scheduled research/monitoring workflows**: Set up ongoing benchmarking cadence

## Technical Details

### Benchmark Configuration
- **Dataset**: Every stored 2026 slate replayed through production optimizer
- **Seed**: Deterministic (seed 2026)
- **Variants**:
  - `baseline` — validated production knobs
  - `knob:*` — one knob flipped per variant (marginal ablations)
  - `temp:*` — sampling-temperature variants with geometric spread
- **Metrics per variant/slate**: placement, gap-to-winner, beat-median rate, payout capture
- **Output**: `benchmark_results.json` + `MODEL_RESEARCH_BENCHMARK.md`

### Execution Notes
- **Sharding**: 20 independent workflow jobs (`--shard-index`/`--shard-count`), plus a `prefetch` job (exports validated game identity once) and a `merge` job
- **Environment**: no per-shard database credentials needed — `prefetch` uses `BACKUP_DATABASE_URL` (read-only) once, shards run off that artifact + the verified corpus snapshot from the `backups` branch
- **Cost**: manually dispatched only; this is a real GitHub Actions compute commitment (~86 CPU-hours), not something to fire off casually — confirm with the operator before dispatching
- **Expected duration**: ~4.3h per shard against the 350-minute per-job timeout

## How to Restart
1. Confirm `main` includes PR #33 (`git log --oneline -1 -- wnba-oracle/scripts/build_model_research_benchmark.py`)
2. Dispatch `model-research-benchmark.yml` via `workflow_dispatch` (defaults: `n_samples=3500`, `temperature_variants=4`, `min_eligible_slates=60`)
3. Monitor shard completion (`gh run watch` / `gh run view`)
4. Download shard artifacts and run `--merge-shards shard*/benchmark_results.json --output-dir merged/`
5. Read the generated `MODEL_RESEARCH_BENCHMARK.md`; cross-reference against `MODEL_PICK_POSTMORTEM_2026-08-28.md` if it exists
6. Open a PR for any evidence-gated knob change; do not promote a knob off a single-slate result

## References
- **PRs**: #26 "Add model research benchmark script", #33 "fix(benchmark): use production's game-identity path; gate coverage before compute"
- **Module**: `wnba-oracle/scripts/build_model_research_benchmark.py`
- **Tests**: `wnba-oracle/tests/unit/test_model_research_benchmark.py`
- **Docs**: `wnba-oracle/README.md` ("Model research benchmark" section), `wnba-oracle/STATUS.md`
- **Real-money motivation**: `wnba-oracle/MODEL_PICK_POSTMORTEM_2026-08-28.md`

---

**Note**: as of 2026-08-29 the benchmark code is merged and fixed, but the sweep itself has never successfully run end to end. Do not delete this file again until a merged `MODEL_RESEARCH_BENCHMARK.md` exists.
