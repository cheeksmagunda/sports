# eval/ deliverable bundle

These five JSON artifacts are the rotation-gate inputs.

- **crps_by_cohort.json**: CRPS (continuous ranked probability score)
  per cohort (G/F/C). Computed by `oracle-rotate-check` from
  `model_shadow_runs` post-tip rows.
- **reliability.json**: nominal vs empirical coverage at P10/P50/P90
  per cohort. Diagram lives at `reliability.png`.
- **conformal_coverage.json**: Mondrian CQR per-cell coverage table.
  Each cell is (cohort, home_away, b2b_rested).
- **rbo_at_5.json**: per-slate RBO@5 between challenger and incumbent
  rankings. Plus the 7-day rolling bootstrap CI.
- **picker_ev_bootstrap.json**: bootstrap CI for the picker's EV vs
  the heuristic baseline. 1000 resamples per Part 6.14.

All five start as placeholders until the live collector has ~30
slates of data. Re-run `scripts/seed_eval_bundle.py` to reseed,
and `oracle-rotate-check --window-days 7` to refresh from the
rotation-gate side.
