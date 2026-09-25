# Offline schedules (continuous slate)

`schedules.csv` is a slim CC BY 4.0 extract of nflverse/nfldata games for
seasons 2002-2026 (REG + postseason). Used for continuous week/slate discovery
without Real Sports auth. See `../../DATA_ATTRIBUTION.md`.

The trailing `gametime` column is nflverse's `HH:MM` US Eastern kickoff
(joined by `game_id` from upstream `games.csv` on 2026-09-24). It is optional:
a CSV without it still loads, with every `ScheduledGame.kickoff_at` left None.
