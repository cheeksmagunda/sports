# NFL #91 live contract verification - handoff to new session

Status: ready
Created: 2026-09-08
Owner: new session, continuing from sports-closeout-parts-a-e-b75cbf

Parts A-E of tonight's close-out are done and merged (see
`drive/2026-09-08-nfl-closeout-handoff.md`). This is a distinct follow-on
task: verify issue #91 (live five-card contract) against real historical
Real Sports NFL contest data. Do this as its own tracked work against issue
#91 - do not fold it into #89, which is closed out.

## Corrected premise - read this first

A prior session's `drive/2026-09-02-nfl-endpoint-archaeology.md` scanned
contest ids 2120-2144 on 2026-09-02 and found no *current/upcoming* NFL
contest in that range, and speculated NFL contests are created fresh close
to game day. That is only evidence about the *current* week, scanned in an
id neighborhood chosen because it was near other sports' *concurrently
active* contests that day. It is NOT evidence about history.

The operator states NFL contests go back roughly two seasons on this
platform. If true, historical NFL contests exist at much lower contest ids
than the 2100s range, and are very likely still queryable (settled/finalized
contests on this platform have stayed queryable for other sports per
existing WNBA research - see `contest_stats.py` / `/entries` /
`/payoutinfo` usage). Do not assume either claim; verify live, and correct
`drive/2026-09-02-nfl-endpoint-archaeology.md` (or add a dated addendum) with
whatever you actually find - don't silently overwrite disputed history.

One concrete lead already in the repo: `nfl-oracle/STATUS.md`'s
`offline_rule_notes` (see `slot_weights_and_scoring` in
`nfl_oracle/providers/RULES_OFFLINE.md` / `strategy/gates.py`) references
`OBSERVED_DEFAULT_SLOT_MULTIPLIERS` derived from "draftinfo defaultMultipliers
(contests 1069/870/1070; byte-identical on non-NFL 2124)". It is NOT clear
from that note alone whether 1069/870/1070 are NFL contests or another
sport. Resolving that ambiguity (`GET /games/playerratingcontest/{id}` for
each of 1069, 870, 1070 and reading the `sport` field in the response) is
probably the fastest first step toward finding a real historical NFL
example.

## What's confirmed and usable right now

- **Auth ("master session")**: `wnba-oracle/scraper/storage_state.json`
  (mode 0600, present) is the shared Real Sports session. nfl-oracle's own
  auth probe already finds it via its sibling-path fallback:
  `uv run --package nfl-oracle nfl-provider-status --json` reports
  `"auth": {"usable": true, ...}` right now, no new login needed.
- **Device identity**: use `NFL_DEVICE_UUID=f3c41b82-e8e6-437a-8e32-b9e52f37d9ed`
  (operator-provided) for header-harvest calls; `NFL_DEVICE_NAME` is unset,
  set one if the code requires it (check `realsports.py`).
- **Railway token**: the operator is rotating `RAILWAY_TOKEN` directly in the
  Codespace themselves (`railway.app` dashboard -> new token -> `gh secret
  set RAILWAY_TOKEN --app codespaces`). Do not attempt this from the Mac or
  paste any token value into a session transcript - if you see one, treat it
  as compromised and tell the operator to rotate again. Not blocking
  anything tonight since nfl-oracle has no deploy source yet.
- **Auth mechanics**: `wnba_oracle.ingest.realsports` (sport-agnostic) has
  both a Playwright path (`headers_or_capture`, needs a browser binary - not
  installed on this Mac; `playwright install chromium` first if you need it)
  and a pure-httpx path (`_http_headers`, `load_cached_headers`) that reuses
  headers already sitting in the storage state without launching a browser.
  The 2026-09-02 archaeology session used the httpx path successfully -
  prefer it.
- **Known-good endpoint shapes** (from the WNBA precedent, same platform):
  `BASE = https://web.realapp.com`,
  `GET /games/playerratingcontest/{contest_id}`,
  `GET /games/playerratingcontest/{contest_id}/draftinfo`,
  `GET /games/playerratingcontest/{contest_id}/stats`,
  `GET /games/playerratingcontest/{contest_id}/payoutinfo`.
  Full registry in `drive/2026-09-02-nfl-endpoint-archaeology.md`.
- `drive/discover_nfl_contest.py` exists for live contest-id sniffing via a
  headless browser; needs `playwright install chromium` on this Mac first.

## Hard rule for this whole task

Stay strictly read-only. GET requests only. Never PUT/POST, never call
anything that could enter, join, or mutate a contest. nfl-oracle's own
`CLAUDE.md` already says this: "Live ingest is read-only: never enter
contests or mutate provider state." Nothing about verifying #91 requires
writing anything to Real Sports - only reading finalized/historical contest
data to check it against `nfl_oracle/providers/RULES_OFFLINE.md`'s
"best-effort" assumptions.

## Suggested next steps

1. Resolve whether contests 1069/870/1070 are NFL (GET each, read `sport`).
2. If not, or to get more examples: use the httpx path with the master
   session to probe a range of low contest ids for `sport == "nfl"`, or ask
   the operator directly for a known historical NFL contest id/URL - much
   faster than blind scanning.
3. For each real NFL contest found, capture `draftinfo`, `stats`, and
   `payoutinfo` responses (save under `drive/nfl_fixtures/`, same convention
   as the 2026-09-02 report) and compare against every entry in
   `nfl_oracle/providers/RULES_OFFLINE.md`'s unknown-rules list: roster/
   inventory eligibility, duplicate-card rules, lock semantics, multiplier-
   bonus pre-lock visibility, negative-value scoring branch, submission
   payload shape.
4. Update `nfl_oracle/providers/auth_status.py`'s or `five_card.py`'s
   `ProviderContractStatus` only if evidence genuinely closes a gap - do not
   flip `provider_contract_verified` or anything touching `contest_entry`
   without explicit findings backing it, and never as a side effect of
   "getting a check to pass."
5. Write findings into `nfl-oracle/STATUS.md` and comment on issue #91 with
   the evidence, same standard as tonight's A6 review: quote the actual
   response fields, don't assert from memory.
6. This is real product-decision-adjacent work (it can inform whether
   `provider_contract_verified` ever flips) - if a finding implies contest
   entry could safely be considered, that is exactly the kind of decision to
   surface to the operator rather than make silently, per root `AGENTS.md`.
