status: IN_PROGRESS
last_verified: 2026-05-27T01:05:38Z
phase: step_1_scaffold

# Build status

Set by the build automation. Allowed values: `IN_PROGRESS`,
`BLOCKED_NONFATAL`, `BUILD_COMPLETE`.

The `last_verified` timestamp is updated by `scripts/dev.sh` on a successful
credential pass. The `phase` field tracks which of the ten ordered build
steps in the handoff is currently in flight.
