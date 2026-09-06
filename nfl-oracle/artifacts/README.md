# Walk-forward evaluation artifacts

Offline **observation-only** reports comparing classical Real-value baselines
(`global_mean`, `position_mean`, `position_median`, `player_mean`) against
optional `feature_ridge` on fixture or local Corpus G labels.

## Checked-in sample

- `walk_forward_fixture_sample.json` / `.md` — small report from
  `tests/fixtures/value_labels` (CI-safe; illustrative metrics only).

## Generate / refresh

```sh
make -C nfl-oracle walk-forward-report
# or
uv run --package nfl-oracle nfl-walk-forward-report
```

Defaults write the sample stem plus `walk_forward_latest.{json,md}` here.
Generated latest / timestamped files are gitignored; the sample pair is kept.

Dry-run and submit gates are **unchanged** (`contest_entry=false`).
