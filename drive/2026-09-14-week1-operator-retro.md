# Week 1 retro: operator observations

Status: ready
Created: 2026-09-14
Owner: operator (transcribed from handwritten notes, 2026-09-14)

Raw observations from the operator, watching week 1 play out in real time.
Organized below into picks/model versus infrastructure, kept in his own
words; a short "session context" line is added under each where this
session already has independent evidence, clearly marked as separate from
the observation itself.

## Picks and model

- **No defensive players were picked** in any lineup all week.
- **K. Walker on MNF was a good pick.**
- **Opening night (Thursday) and MNF were the best** slates for pick quality.
- **The Thursday Australia game and Sunday were bad** for pick quality.
- **Chalk picks on Sunday were also wrong.** Flagged as concerning
  specifically because this was still the pre-boost regime, where the
  "obvious" picks should be the easiest to get right.
  - Session context: STATUS.md's own historical archive analysis backs up
    why this is concerning: in the four real zero-boost week-1 contests it
    studied, winners captured 97.5% of hindsight-best and 59 of 80 visible
    lineups had all five picks inside the real-value top ten. Pre-boost is
    supposed to be the easy case where the serious field converges; getting
    even the chalk picks wrong there is a stronger signal than it would be
    once boosts add real variance.
- **No model changes have been made since Monday.**

## Infrastructure

- **Boosts stayed flat at zero all week** (the provider's popularity/
  performance boost scale runs 0.0-3.0; week 1 never left 0.0).
  - Session context: confirmed independently, STATUS.md and the boost
    watcher log both show all-zero every check since week 1 start; this is
    expected and scheduled to end week 2 Thursday, not a bug.
- **The app crashed** around the Thursday Australia game / Sunday window.
  - Session context: this matches a real, already-diagnosed bug, not a
    one-off: the Sunday 2026-09-13 T-40 freeze refused three times and
    produced zero picks, root-caused to a pool-completeness check measured
    against the whole day's roster instead of only games still ahead of
    kickoff. Fixed in
    [PR #158](https://github.com/cheeksmagunda/sports/pull/158),
    tracked in
    [issue #156](https://github.com/cheeksmagunda/sports/issues/156).
