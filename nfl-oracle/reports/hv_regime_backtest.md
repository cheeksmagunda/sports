# HV/TDV board backtest, split by slate regime (#603)

Generated 2026-09-28T12:16:32-05:00.

Success metric is the Highest value board only: top-5 hits, and
the share of that top 5's displayed Value the hits carry.
Draft count and win frequency are not scored.

Sunday multi-game and one-night (TNF, SNF, MNF) are separate samples.
A rate measured on Sunday is not a MNF rate.

Board pool: the visible Highest value section in the screenshots.
That is not the full roster. Players off the board are absent.
The optimizer counterfactual uses realized base as a perfect
projection, then the live boost-rank blend, then picks five.
It is not a walk-forward fit. Corpus C is empty, so the production
model was not replayed.

## Command

```sh
scripts/hv_regime_backtest.py --out reports/hv_regime_backtest.json --report reports/hv_regime_backtest.md
```

## Sunday boards

### 2026-09-20 `sunday_multi` law residual max 0.20

HV/TDV top 5: Brandon Aubrey, Spencer Shrader, Tre Tucker, Jaylen Waddle, CeeDee Lamb

HV/TDV top 5 positions: 2 K, 0 DEF, 3 skill.

| policy | HV hits | HV Value capture | K | DEF |
|---|---|---|---|---|
| identity_uncapped | 4 | 81.3% | 2 | 0 |
| boost_0.75_uncapped | 3 | 61.3% | 1 | 0 |
| boost_0.75_def1 | 3 | 61.3% | 1 | 0 |
| boost_0.75_k1 | 3 | 61.3% | 1 | 0 |
| boost_0.75_def1_k1 | 3 | 61.3% | 1 | 0 |

### 2026-09-27 `sunday_multi` law residual max 0.20

HV/TDV top 5: Chris Boswell, Sam Darnold, Will Anderson Jr., Harold Fannin Jr., Genesis Smith

HV/TDV top 5 positions: 1 K, 2 DEF, 2 skill.

| policy | HV hits | HV Value capture | K | DEF |
|---|---|---|---|---|
| identity_uncapped | 5 | 100.0% | 1 | 2 |
| boost_0.75_uncapped | 4 | 79.7% | 1 | 2 |
| boost_0.75_def1 | 4 | 79.7% | 1 | 1 |
| boost_0.75_k1 | 4 | 79.7% | 1 | 2 |
| boost_0.75_def1_k1 | 4 | 79.7% | 1 | 1 |

## Mean HV/TDV board rate by regime

Hit rate is hits/5 on the board top 5. Value capture is the
share of that top 5's displayed Value. `identity_uncapped` is
the optimizer when the projected base is already the realized
base. `boost_0.75` is the live blend on that correct base.
One-night columns stay empty when no one-night board was scored.

| policy | sunday_multi hits | sunday_multi Value | one_night hits | one_night Value |
|---|---|---|---|---|
| identity_uncapped | 90.0% (n=2) | 90.7% (n=2) | n/a (n=0) | n/a (n=0) |
| boost_0.75_uncapped | 70.0% (n=2) | 70.5% (n=2) | n/a (n=0) | n/a (n=0) |
| boost_0.75_def1 | 70.0% (n=2) | 70.5% (n=2) | n/a (n=0) | n/a (n=0) |
| boost_0.75_k1 | 70.0% (n=2) | 70.5% (n=2) | n/a (n=0) | n/a (n=0) |
| boost_0.75_def1_k1 | 70.0% (n=2) | 70.5% (n=2) | n/a (n=0) | n/a (n=0) |

`one_night_tnf` boards scored: 0. HV/TDV rate: not run.

`one_night_snf` boards scored: 0. HV/TDV rate: not run.

`one_night_mnf` boards scored: 0. HV/TDV rate: not run.

## Contest-day inventory (not an optimizer frequency)

This is the early probe list in `drive/nfl_probe_out` (33 NFL contest days), not the later 91-contest Corpus C sweep. The sweep was not stored per day, so it cannot be split here.

| regime | finalized contest days |
|---|---|
| multi_other | 8 |
| one_game_other | 1 |
| one_night_mnf | 7 |
| one_night_tnf | 7 |
| sunday_multi | 11 |

Same-day SNF sits inside `sunday_multi` when that Sunday also has two or more afternoon games. Those contest ids are not a separate SNF sample. TNF and MNF are their own days.

## MNF T-40 game

2026-09-28 PHI at CHI kickoff 20:15 ET. Regime `one_night_mnf`. Games that day: 1.

## Recommended live knobs

### sunday_multi

- `NFL_OPTIMIZER_PROFILE=max_value`.
- No defender cap and no kicker cap. Slot order stays joint.
- On these two boards, perfect-base identity (the optimizer when the base is already known, n=2) hits the HV/TDV top 5 at 90.0% and captures 90.7% of that top 5's Value. Sep 20's identity five includes two kickers. Sep 27's includes two defenders.
- `boost_0.75` on that same perfect base hits the board at 70.0% and captures 70.5% of the board Value. Max-1 defender and max-1 kicker on the blend captures 70.5%.
- **Do not flip live `NFL_PICKER_BOOST_RANK_BLEND` to 0.75.** Live stays `0` (#637 / Live train). Offline arms still compare identity vs `0.75`. The 2026-09-25 sweep (identity 51.7%, boost 0.75 57.9%, 91 contests) is ridge hindsight capture on a mixture of regimes, not this HV/TDV board metric.

### one_night (TNF / SNF / MNF)

- Keep `NFL_OPTIMIZER_PROFILE=max_value` (floor 1/1) for one-game nights. A two-game floor is the Sunday shape.
- **Do not flip live blend to 0.75.** No one-night HV/TDV board was scored (n=0). Do not copy Sunday perfect-base identity preferences onto a night slate as a live flip.
- Serving code already defaults to max 1 defender, max 1 kicker, and slot-by-mean (#616/#617). This offline table does not authorize a Railway change. Sunday identity lineups used two kickers or two defenders; do not treat that mix as a night-slate quota.
- Do not use the week-1 zero-boost both-quarterback archetype.
- The probe has zero standalone SNF contest days. SNF that shares a Sunday date is inside `sunday_multi`.

