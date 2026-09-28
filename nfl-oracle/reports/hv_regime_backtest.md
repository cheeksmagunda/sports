# HV top-5 vs chalk, split by slate regime (#603)

Generated 2026-09-28T03:27:27+00:00.

Sunday multi-game and one-night (TNF, SNF, MNF) are separate samples.
A rate measured on Sunday is not a MNF rate.

Board pool: the visible Highest value section in the screenshots.
That is not the full roster. Players off the board are absent.
Chalk is the highest draft count on those same rows.
The optimizer counterfactual uses realized base as a perfect
projection, then the live boost-rank blend, then the scoring law
`base * (slot + boost)` with slots assigned by descending projection.
It is not a walk-forward fit. Corpus C is empty, so the production
model was not replayed.

## Command

```sh
scripts/hv_regime_backtest.py --out reports/hv_regime_backtest.json --report reports/hv_regime_backtest.md
```

## Sunday boards

### 2026-09-20 `sunday_multi` law residual max 0.20

HV top 5: Brandon Aubrey, Spencer Shrader, Tre Tucker, Jaylen Waddle, CeeDee Lamb

Chalk top 5: Ja'Marr Chase, CeeDee Lamb, DeVonta Smith, Harrison Butker, Brandon Aubrey

HV vs chalk overlap: 2 of 5.

HV top 5 positions: 2 K, 0 DEF, 3 skill. Chalk top 5: 2 K, 0 DEF, 3 skill.

| policy | HV hits | chalk hits | realized | vs uncapped | K | DEF |
|---|---|---|---|---|---|---|
| identity_uncapped | 4 | 1 | 115.0 | 100.0% | 2 | 0 |
| boost_0.75_uncapped | 0 | 0 | 94.6 | 82.2% | 1 | 3 |
| boost_0.75_def1 | 1 | 1 | 102.0 | 88.7% | 1 | 1 |
| boost_0.75_k1 | 0 | 0 | 94.6 | 82.2% | 1 | 3 |
| boost_0.75_def1_k1 | 1 | 1 | 102.0 | 88.7% | 1 | 1 |

### 2026-09-27 `sunday_multi` law residual max 0.20

HV top 5: Chris Boswell, Sam Darnold, Will Anderson Jr., Harold Fannin Jr., Genesis Smith

Chalk top 5: Jahmyr Gibbs, Sam Darnold, Chris Boswell, Jordan Addison, Jaylen Warren

HV vs chalk overlap: 2 of 5.

HV top 5 positions: 1 K, 2 DEF, 2 skill. Chalk top 5: 1 K, 0 DEF, 4 skill.

| policy | HV hits | chalk hits | realized | vs uncapped | K | DEF |
|---|---|---|---|---|---|---|
| identity_uncapped | 5 | 2 | 121.6 | 100.0% | 1 | 2 |
| boost_0.75_uncapped | 1 | 1 | 97.6 | 80.2% | 1 | 3 |
| boost_0.75_def1 | 1 | 2 | 98.8 | 81.3% | 2 | 1 |
| boost_0.75_k1 | 1 | 1 | 97.6 | 80.2% | 1 | 3 |
| boost_0.75_def1_k1 | 1 | 2 | 97.1 | 79.9% | 1 | 1 |

## Mean top-5 rate by regime

Rate is hits/5. `identity_uncapped` is the optimizer when the
projected base is already the realized base. `boost_0.75` is the
live blend applied on top of that correct base, which reassigns
the value table in boost order. One-night columns stay empty
when no one-night board was scored. They are not the Sunday rate.

| policy | sunday_multi HV | sunday_multi chalk | one_night HV | one_night chalk |
|---|---|---|---|---|
| identity_uncapped | 90.0% (n=2) | 30.0% (n=2) | n/a (n=0) | n/a (n=0) |
| boost_0.75_uncapped | 10.0% (n=2) | 10.0% (n=2) | n/a (n=0) | n/a (n=0) |
| boost_0.75_def1 | 20.0% (n=2) | 30.0% (n=2) | n/a (n=0) | n/a (n=0) |
| boost_0.75_k1 | 10.0% (n=2) | 10.0% (n=2) | n/a (n=0) | n/a (n=0) |
| boost_0.75_def1_k1 | 20.0% (n=2) | 30.0% (n=2) | n/a (n=0) | n/a (n=0) |

Sunday HV-list vs chalk-list overlap, before any optimizer: 40.0% (n=2).

`one_night_tnf` boards scored: 0. Optimizer HV/chalk rate: not run.

`one_night_snf` boards scored: 0. Optimizer HV/chalk rate: not run.

`one_night_mnf` boards scored: 0. Optimizer HV/chalk rate: not run.

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
- On these two boards, perfect-base identity (the optimizer when the base is already known, n=2) put HV-board players in the top 5 at 90.0% and chalk at 30.0%. Sep 20's identity five includes two kickers. Sep 27's includes two defenders. A max-1 cap on both drops the blended arm to 84.3% of that identity lineup.
- Do not chase Sunday draft-count chalk. HV top 5 and chalk top 5 overlap 40.0%.
- Do not read `boost_0.75` as the knob that finds this board once the base is known. On the same perfect base it hits HV top 5 at 10.0% and captures 81.2%, because the blend reassigns a correct value table toward boost order.
- Leave the live ridge blend at `NFL_PICKER_BOOST_RANK_BLEND=0.75` until a regime-split refit replaces it. The 2026-09-25 sweep (identity 51.7%, boost 0.75 57.9%, 91 contests) is that ridge on a mixture of regimes. It is not this table and it is not MNF.

### one_night_mnf (tonight), and TNF / SNF

- Tonight is one game, PHI at CHI. Keep `NFL_OPTIMIZER_PROFILE=max_value` (floor 1/1). A two-game floor is the Sunday shape.
- Keep `NFL_PICKER_BOOST_RANK_BLEND=0.75` as the live ridge setting. Do not flip it to identity because the Sunday perfect-base table prefers identity. That table is Sunday, and it assumes the base is already known. No one-night board was scored (n=0).
- Do not add a defender cap or a kicker cap. Nothing one-night was measured, and the Sunday identity lineups use two kickers or two defenders. Do not copy that mix onto MNF as a quota.
- Do not use the week-1 zero-boost both-quarterback archetype. Those four contests mix Thursday, Friday, Sunday, and Monday, and the boost table was all zeros. Tonight is week 3. Sunday's board already shows boosts up to +3.0x.
- Slot-by-mean stays off.
- The probe has zero standalone SNF contest days. SNF that shares a Sunday date is inside `sunday_multi`.

