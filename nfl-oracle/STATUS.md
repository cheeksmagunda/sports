# Status


## Land note (2026-09-25)
<!-- tip-edacd4b2-land -->
- PR #330 tip restored FILES.md + ruff format; awaiting green CI then Railway boost_0.75 flip.
## Picker knobs Corpus C sweep (2026-09-25 ~17:02 CT, Refs #280)

Boost-aware projection + optional holdout position calibration, applied after
`predict` and before `optimize` (`nfl_oracle.recommendations.picker_knobs`).
Defaults remain identity. Env knobs: `NFL_PICKER_BOOST_RANK_BLEND`,
`NFL_PICKER_POSITION_CALIBRATION`, `NFL_PICKER_PROFILE`.

### Corpus C results

- `NFL_PICKER_BOOST_RANK_BLEND=0.75` with `NFL_PICKER_PROFILE=boost_0.75` was
  selected for the post-merge Railway flip once CI is green.
- `NFL_PICKER_POSITION_CALIBRATION` remains unset/default identity for this
  rollout.

### Verification notes

- Keep `FILES.md` intact; the PR tip restores it after the accidental bot-authored
  commit.
- The branch tip was prepared for a small docs-only commit to retrigger Actions
  under the human GitHub identity.
