# Walk-forward evaluation report

Observation only — no contest entry. Dry-run/submit gates unchanged.

- **root:** `tests/fixtures/value_labels`
- **fixture_mode:** `True`
- **labels:** 21
- **seasons:** [2022, 2023, 2024, 2025]
- **methods:** ['global_mean', 'position_mean', 'position_median', 'player_mean', 'feature_ridge']

## Pooled ranking (lower MAE better)

| rank | method | n | mae | rmse | bias |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | `position_mean` | 13 | 0.628846 | 0.714700 | 0.014744 |
| 2 | `position_median` | 13 | 0.688462 | 0.754601 | -0.019231 |
| 3 | `player_mean` | 13 | 0.736538 | 0.875537 | 0.160897 |
| 4 | `feature_ridge` | 13 | 0.749945 | 0.867349 | 0.031458 |
| 5 | `global_mean` | 13 | 1.345192 | 1.535630 | 0.125321 |

## feature_ridge vs best baseline

- best_baseline: `position_mean`
- feature_ridge_mae: `0.7499454541536159`
- best_baseline_mae: `0.6288461538461539`
- delta_mae (ridge − best): `0.12109930030746197`
- feature_ridge_better: `False`
- note: Negative delta_mae means feature_ridge has lower pooled MAE than the best classical baseline (lower is better).

## Notes

- Walk-forward by season on Corpus G anchors only (shadow / observation).
- No contest submission or live entry code paths are exercised.
- Unseen positions fall back to the global prior from the train window.
- player_mean falls back to position then global; identity continuity across anchors is unaudited.
- feature_ridge is optional: ridge on live_ok prior features only; never uses same-slate finals or label value as inputs.
- Eval report ranks pooled MAE across classical baselines and feature_ridge.
- Fixture-scale metrics are illustrative only; not contest decision value.
- Dry-run/submit gates are unchanged (contest_entry remains false).
