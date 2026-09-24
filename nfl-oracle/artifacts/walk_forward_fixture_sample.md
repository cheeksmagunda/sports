# Walk-forward evaluation report

Observation only — no contest entry. Dry-run/submit gates unchanged.

- **root:** `data/raw/corpus_g`
- **fixture_mode:** `False`
- **labels:** 47206
- **seasons:** [2024, 2025]
- **methods:** ['global_mean', 'position_mean', 'position_median', 'player_mean', 'feature_ridge']

## Pooled ranking (lower MAE better)

| rank | method | n | mae | rmse | bias |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | `position_median` | 23955 | 0.783188 | 1.246630 | -0.340876 |
| 2 | `feature_ridge` | 23955 | 0.798680 | 1.129402 | 0.073970 |
| 3 | `player_mean` | 23955 | 0.798682 | 1.129410 | 0.074018 |
| 4 | `position_mean` | 23955 | 0.857808 | 1.194447 | 0.042790 |
| 5 | `global_mean` | 23955 | 0.934748 | 1.271116 | 0.045048 |

## feature_ridge vs best baseline

- best_baseline: `position_median`
- feature_ridge_mae: `0.7986802208200159`
- best_baseline_mae: `0.7831882313162958`
- delta_mae (ridge − best): `0.015491989503720105`
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
