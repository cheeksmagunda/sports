# nhl-oracle

NHL Oracle application scaffold.

Current scope is a pre-provider-access scaffold exercised only against
synthetic fixtures: package wiring, boundary-safe layout, verification
targets, a candidate contest contract and audit gates (`contract/`), a
redacted payload provenance store (`ingest/`), an identity map and collision
reconciler (`identity/`), and a freeze-cycle job skeleton (`scheduler/`). No
live NHL provider, model, optimizer, hosted API, frontend, or deployment
exists yet; see `STATUS.md` for current detail.

## Connection surfaces

Use root `../ENTRY_POINTS.md` for the portfolio-wide Codespace, agent, auth,
and cloud project rules. For NHL work, open or rejoin the repo's GitHub
Codespace, read root `../AGENTS.md`, this app's `AGENTS.md`, this `README.md`,
and `STATUS.md`, then run from the monorepo root:

```sh
make test-app APP=nhl-oracle
scripts/auth-check nhl-oracle --offline
```

NHL has no Railway production project yet. Do not create Railway services,
provider credentials, contest entry paths, or per-agent PATs unless a scoped
issue explicitly authorizes that work. Cloud projects must include the root
snapshot bundle plus `nhl-oracle/AGENTS.md`, `nhl-oracle/README.md`, and
`nhl-oracle/STATUS.md`, then verify against live `main` before material work.

## Commands

From this directory:

```sh
make test
make lint
make typecheck
```

From the repository root:

```sh
make test-app APP=nhl-oracle
make check-applications
make check-boundaries
```

## Roadmap

The approved plan from the current scaffold to a verified, autonomous
recommendation product (planned under #135, 2026-09-10; moved here from the
issue tracker 2026-09-24). Milestone progress lives in `STATUS.md`. The plan
itself authorizes no provider collection, service provisioning, credentials,
or deployment; each milestone gets its own scoped issue when it starts.

Working product hypothesis, pending operator confirmation: open the NHL app
and see five ordered Real Sports recommendations for manual entry. Week 2
live audit (#299) confirmed five-card-ordered format, per-contest lock, flat
boosts, score label "value", goalie eligibility, and slot multipliers
(2.0/1.8/1.6/1.4/1.2) from Real Sports NHL evidence (historical contest 1901
plus current-slate player cards).

1. **Product and provider contract.** Audit current and historical contest
   identities, exact score/value labels, candidate completeness, goalie
   eligibility, slot multipliers, boosts, and whether lock applies to a
   contest or to individual games. Deliver redacted fixtures and executable
   contracts. Do not assume NFL or WNBA routes or scoring apply.
2. **Historical corpora.** Build NHL-owned historical game/player and contest
   corpora. Reconcile source IDs, retain provenance and capture/event/
   availability clocks, report coverage with denominators, and separate
   pregame evidence from finalized outcomes. Official hockey statistics may
   provide features but do not substitute for authoritative Real value or
   contest outcomes.
3. **Predictions.** Start with named player and position baselines, then test
   skater and goalie approaches where eligible. Candidate inputs: expected
   ice time, even-strength and power-play role, shot volume, opponent, rest,
   scratches, starting-goalie evidence. Chronological evaluation with actual
   pre-decision availability; report uncertainty, cold starts, and input
   gaps. Added complexity needs out-of-sample evidence.
4. **Optimization under the verified contest law.** Compare candidate
   selection and committed slot assignment against exhaustive small
   fixtures. Replay frozen decisions against finalized outcomes, with
   explicit uncertainty/censoring for incomplete contest archives. No payout
   probabilities from synthetic fields.
5. **Hosted lifecycle.** Retained validated model before freeze; pregame
   pool/context refresh; prediction and optimization; lock recheck;
   append-only freeze; read-only API and mobile frontend; postgame
   reconciliation. One active writer, durable private runtime inputs,
   bounded retries, recoverable checkpoints, prior artifacts retained for
   rollback.
6. **Verified autonomous delivery** on a natural NHL slate. A healthy service
   is not sufficient: source freshness, active model, committed freeze, API
   payload, and actual five-card mobile rendering must all be verified.

Operational lessons carried over from the NFL 2026-09-09 run:

- Model training/validation must finish before the time-critical freeze job.
- Expose meaningful phases and safe failure codes; no single "waiting" state
  covering collection and model work.
- Define a measured publication-latency target and pre-deadline readiness
  checks. T-40 is a candidate policy, subject to NHL lock behavior and late
  lineup evidence.
- Failures must preserve previous valid freezes; stale or blocked states must
  be explicit.

Open decisions (operator): first product scope, initial target slate/date,
usable historical coverage depth beyond the Week 2 seed, and the publication
target after a measured hosted rehearsal. Contest law and lock semantics were
verified in the Week 2 live audit (#299); see STATUS.md.
