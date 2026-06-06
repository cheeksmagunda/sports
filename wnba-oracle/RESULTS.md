# RESULTS ledger

Live contest-performance log for the WNBA Oracle daily-draft picker.
One section per slate, newest first. This is the scoreboard the whole
build exists to move: contest-payout EV, not raw prediction accuracy
(see README "Strategy").

Verified facts are tagged `[verified]` (observed in the Real Sports app
or read from our own DB). Synthesized reasoning is tagged `[reasoned]`.
Numbers read off an in-app screenshot are tagged `[screenshot]` until a
finalized leaderboard row backs them.

Provenance note: the lineup generator (cron-job2 freeze) writes the
frozen lineup to Redis + Postgres, not to git. The session that produced
the slate below errored before it could log anything here, so this first
entry is reconstructed from the operator's in-app screenshots. Going
forward, append an entry per slate from the frozen `lineup_json` plus the
finalized leaderboard row.

To finalize a slate without a screenshot, once dayclose has ingested the
contest run `oracle-results --slate-date YYYY-MM-DD`. It reads the canonical
Postgres store (`frozen_lineups` + `slate_labels` + `contest_leaderboards`)
and appends a finalized entry directly below the marker. Note: the DB stores
only the top-20 finishers, so the auto entry reports the realized total and
the gap to the winner but cannot recover our exact rank or the field size
(e.g. "517th of 8.7k") — backfill those two from a screenshot if wanted.

---

<!-- AUTO-APPEND-BELOW -->

## Slate 2026-05-28 (live / finalizing 2026-05-29) — STRONG START

Status: in progress when observed. 2 of 5 picks had tipped off.
Standing at observation: **11.51 points, Top 10%, 517th of 8,700 entries**
`[screenshot]`. Not yet finalized; refresh once the leaderboard locks.

### The lineup

Slot order is highest-confidence pick first. The "mult" column is the
boost multiplier shown on the draft card; "line" is the card_boost the
player must clear; "live value" is what the app showed mid-slate for
players who had already played.

| Slot | Player              | Mult  | Line | Live value      | Drafts | Notes |
|------|---------------------|-------|------|-----------------|--------|-------|
| 1    | M. Siegrist         | 5.0x  | 1.5  | 7.6 (1st value) | 444    | played; carrying the card `[screenshot]` |
| 2    | C. Zandalasini      | 4.8x  | —    | not yet played  | —      | pending |
| 3    | C. Parker-Tyus      | 4.6x  | 0.9  | 4.3 mid, then faded | 23     | played; mid pick that stopped performing `[screenshot]` |
| 4    | R. Johnson          | 4.4x  | —    | not yet played  | —      | pending |
| 5    | G. VanSlooten       | 4.2x  | —    | not yet played  | —      | pending |

`[screenshot]` for every cell above. Player first names are abbreviated
as the app displays them; do not expand without confirming identity.

### Why these picks (rationale)

The lineup is the output of the corrected optimizer (D42/D43) reading the
EB-shrunk artifact (D44/D45), under the shared-scope env knobs that were
live at fire time:

- `CONTRARIAN_STRENGTH=0.2` — anti-popularity tilt `[verified, STATUS]`
- `CONTRARIAN_ENABLED=true` `[verified, STATUS]`
- `OPTIMIZER_MAX_PER_TEAM=2` — no 3-from-one-team cannibalization `[verified, STATUS]`
- `PAYOUT_REGIME=top_20` — convex-above-the-line EV, mild contrarianism `[verified, settings.py]`
- Slot multipliers `[2.0, 1.8, 1.6, 1.4, 1.2]` (the corrected WNBA scheme, D42) `[verified]`

What the result is telling us, pick by pick:

- **M. Siegrist (slot 1).** The smart part of this lineup is that slot 1 is
  NOT a contrarian pick. 444 drafts, full chalk, and it is the single
  highest-value card on the whole board at 7.6 `[screenshot]`. Putting the
  highest-confidence, widely-owned name in the top slot (which carries the
  2.0 slot multiplier, the largest in the ladder) is exactly the right call:
  the slot-1 multiplier rewards the pick you are most sure clears its line,
  and chalk is chalk because the field also believes it. The contrarian tilt
  is a tiebreaker among comparable picks, not a mandate to fade the obvious
  stud. Anchoring the card on a high-floor chalk play and then spending the
  contrarian leverage in the lower slots (see Parker-Tyus) is the whole game:
  protect the floor up top, reach for low-ownership upside below. Siegrist
  cleared a 1.5 line and ran away with it. `[reasoned]`
- **C. Parker-Tyus (slot 3).** Honest update: this one did not cash. She
  was the deep-contrarian leg (only 23 drafts across the whole field
  `[screenshot]`, i.e. almost nobody else rostered her), and the
  anti-popularity penalty in `picker/popularity.py` is exactly what
  surfaces a name like this above more-popular alternatives. Early in the
  slate she flashed (the 4.3 value in the screenshot was a mid-slate
  snapshot, 1st in her band at that moment), but she was a **mid pick that
  stopped performing** and faded as the game went on. The lesson is not
  that the contrarian reach was wrong in process — low ownership on a
  cleared line is real leverage when it hits — but that it is a
  higher-variance bet, and an in-progress value reading is a snapshot, not
  a final. The card's strong standing was carried by the slot-1 chalk
  anchor, not by this leg. Tag the early "hit" framing as premature; the
  finalized real_score is what the entry below will settle. `[reasoned]`
- **Zandalasini / R. Johnson / VanSlooten (slots 2, 4, 5).** Still to play
  at observation. These fill the back half of the card under the
  `max_per_team=2` constraint and the slot-multiplier ladder; their value
  is unrealized, so the 517th-of-8.7k standing was earned by just two of
  the five players. Upside is still on the board. `[reasoned]`

### Read-through

Two of five players in, the entry reached Top 10% / 517th of 8,700
`[screenshot]`. Read it honestly: the standing was carried by the slot-1
chalk anchor (Siegrist, wide-margin clear), not by the contrarian leg.
Parker-Tyus flashed early then faded to a mid finish, which is exactly the
variance profile of a 23-draft reach. So the process read is the right
one — anchor the floor on chalk up top, take the low-ownership swing
below — but the slate is a reminder that the swing legs are higher
variance and an in-progress value is a snapshot, not a result. One slate,
not yet finalized: a signal, not proof. Log the final standing here once
the leaderboard locks, and start an entry for every subsequent slate so we
can tell EV from variance over a real sample.

### To finalize this entry

```
# once the contest is final, pull the frozen lineup + leaderboard row
set -a && source .env && set +a
# read the frozen lineup_json + realized per-player real_score from Postgres
# (slate_labels / contest_leaderboards), confirm the standing, and replace
# the [screenshot] tags with [verified] plus the final rank/points.
```

---

## Template for the next slate

```
## Slate YYYY-MM-DD — <one-line headline>

Status: final | in progress
Standing: <points> points, <percentile>, <rank> of <field size>

| Slot | Player | Mult | Line | Realized value | Drafts | Notes |
|------|--------|------|------|----------------|--------|-------|

### Why these picks
- env knobs at fire time:
- per-pick rationale:

### Read-through
- what worked, what didn't, EV vs variance read
```
