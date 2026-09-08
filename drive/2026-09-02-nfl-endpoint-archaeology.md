REAL SPORTS NFL ENDPOINT ARCHAEOLOGY REPORT

A. EXECUTIVE RESULT
--------------------
LARGELY RESOLVED as of this session. The prior blocker (Chrome extension /
CDP automation being flaky or disconnected) is now irrelevant: this session
bypassed the browser-automation path entirely and hit the live API directly
with httpx, reusing WNBA Oracle's existing Real Sports auth machinery
(`headers_or_capture`, `_http_headers` from
`wnba-oracle/src/wnba_oracle/ingest/realsports.py`), which is sport-agnostic.
That auth code was already sitting in this repo and requires no browser
extension at all for authenticated GETs — Playwright is only needed once, to
mint or refresh `scraper/storage_state.json` (already fresh from earlier
today) or to sniff a contest id from network traffic, and that Playwright
run is a plain headless `chromium.launch()`, not the Chrome-extension/MCP
path that failed twice.

Result: 6 of 6 targeted NFL endpoints returned live 200 JSON bodies on the
first attempt. A follow-up contest-id sniff (adapting
`discover_wnba_contest_id` to sport `nfl`) and a bounded contest-id range
scan (2120-2144) established that **no NFL playerratingcontest exists yet**
as of 2026-09-02 — the highest live contest id is 2125 (ncaaf, day
2026-09-03); ids 2126-2144 all 403 "Not a valid contest". NFL Week 1 kicks
off 2026-09-09/10, so the NFL contest is presumably created closer to that
date, consistent with the daily creation pattern seen for mlb/soccer/ncaaf.

Remaining gap: sections D, H, J (contest-scoped payload contracts, payout,
pre-lock draft data) stay unverified for NFL specifically, purely because no
NFL contest exists yet to query — not because of any tooling blocker. Re-run
`drive/discover_nfl_contest.py` closer to 2026-09-09 to fill those in.

B. VERIFIED NFL ENDPOINT REGISTRY
-----------------------------------
VERIFIED LIVE (request observed firing from the NFL page in a signed-in
browser session; response body NOT captured):
- PUT  /timesegments                       body seen: {"timeSegments":1}
- GET  /home/nfl/next?cohort=0
- GET  /home/nfl/boostcontrol?cohort=0&day=2026-09-09
- GET  /squads?sport=nfl
- GET  /livefeed/all/feed
- GET  /games/19457/sport/nfl/feed?version=2&view=recent&viewFrame=default

Live page route observed: https://realsports.io/n8gT1tOFAM2 (NFL slate page).

BUNDLE-DERIVED (path/param shape read from shipped frontend JS; sport-generic
templates, `{sport}` confirmed substitutable with `nfl` by analogy to `wnba`
usage in this repo's WNBA ingest code, NOT verified live for nfl):
- GET /home/{sport}/days
- GET /home/{sport}/day/next
- GET /home/{sport}/boostcontrol
- GET /home/loginslate
- GET /players/sport/{sport}/search
- GET /players/sport/{sport}/compare
- GET /players/embedinfo/{playerId}/sport/{sport}
- GET /games/{gameId}/sport/{sport}/feed
- GET /games/{gameId}/sport/{sport}/stats
- GET /games/{gameId}/sport/{sport}/position-graph
- GET /games/{gameId}/sport/{sport}/compete
- GET /games/{gameId}/sport/{sport}/leaderboard
- GET /games/{gameId}/sport/{sport}/checkins
- GET /games/{gameId}/sport/{sport}/light
- GET /games/playerratingcontest/{contestId}
- GET /games/playerratingcontest/{contestId}/view/{userId}
- GET /games/playerratingcontest/{contestId}/draftinfo
- GET /games/playerratingcontest/{contestId}/stats
- GET /games/playerratingcontest/{contestId}/payoutinfo
- PUT /games/playerratingcontest/{contestId}/lineup

WNBA PRECEDENT (confirmed live and in production for wnba via this repo's
ingest code — same platform, different sport, cited as the strongest analogy
for how NFL endpoints likely behave):
- GET  {BASE}/home/{sport}/next               (repo: realsports.py:386,416)
- GET  {BASE}/players/sport/{sport}/search    (repo: realsports.py:362)
- GET  {BASE}/games/{gid}/sport/{sport}/players (repo: realsports.py:439)
- GET  {BASE}/games/playerratingcontest/{contest_id}          (realsports.py:726)
- GET  {BASE}/games/playerratingcontest/{contest_id}/stats    (contest_stats.py:154)
- GET  {BASE}/games/playerratingcontest/{contest_id}/entries  (contest_stats.py:286)
- GET  {BASE}/games/playerratingcontest/{cid}?contestType=sport&source=home
                                                (probe_leaderboard.py:125)
  where BASE = https://web.realapp.com (repo: realsports.py:79)

Note the API host is web.realapp.com, distinct from the realsports.io site
host the browser page loads from. Live NFL requests were observed via
browser network tooling and their exact host was not independently
double-checked against BASE in this session — treat as consistent with WNBA
absent contrary evidence, not separately confirmed.

/entries is present in the confirmed WNBA contest surface but was NOT among
the bundle-derived NFL playerratingcontest routes listed above. This is an
open gap, not a confirmed absence — see section O.

C. NFL PAYLOAD CONTRACTS
--------------------------
VERIFIED LIVE (captured 2026-09-02, saved under drive/nfl_fixtures/):

GET /home/nfl/next?cohort=0  (200, 75769 bytes)
  top-level: days, cohortOptions, latestDay, latestDayContent, latestWeek,
  liveGameInfo, emojiUsages
  latestDayContent: day, week, season, games, replayGames, replayConfig,
  config, upsellInfo, items, groupToGameIds, gamesHeader, headerSource
  games[]: full Real Sports game object (id, sport, season, seasonType,
  status, day, dateTime, week, homeTeamId, awayTeamId, channel,
  homeTeamScore/awayTeamScore, pointSpread, overUnder, homeMoneyline,
  awayMoneyline, homeTeamKey/awayTeamKey, commentCount, impressionCount,
  isFullVisibility, display{...}, plus ~60 more fields shared with other
  sports' game objects)

GET /home/nfl/boostcontrol?cohort=0  (200, 76 bytes — pregame/empty)
  full body: {"header":"Today's players","userPasses":[],
  "shouldUpsell":true,"numMore":0}

GET /squads?sport=nfl  (200, 288 bytes — pregame/empty)
  full body: {"statTrackerInfo":{"header":"Week 1","description":"...",
  "latestDay":"2026-09-09","statTrackerGroups":[]},"squads":[]}

GET /games/19457/sport/nfl/feed?version=2&view=recent&viewFrame=default
  (200, 140869 bytes)
  top-level: game, matchPlayerBoxScores, eventInfo, plays, posts, players,
  upsellInfo, upsellPacks, alertMessage, inviteUpsell, market, hasMarket,
  liveActivityEnabled, messageChannelId, ignoreEmojiUsages, alwysShowValue,
  numLatestPlays, ignoreGameData, boxScoreCategoryTabs, boostInfo,
  upsellReferrals, availableGameFeedViews, defaultGameTab
  players[]: id, sport, teamId, avatar, firstName, lastName, jersey,
  position, injuryStatus, gameId, rankings{primaryRanking, primaryValue,
  secondaryValue, tertiaryValue, quaternaryValue, alltimeRanking,
  alltimeValue, previous*}, seasonAverages, backgroundColor, team{id, sport,
  key, name, displayName, avatar, primaryColorReal, secondaryColorReal,
  conference}

GET /games/19457/sport/nfl/stats  (200, 1443 bytes — pregame/empty)
  top-level: playerBoxScores (empty), gameBoxScore{periods[4],
  teamBoxScores(empty)}, stats{numTimeoutsTotal, onFieldAmount},
  gameTeamComparison{homeTeamStandings, awayTeamStandings,
  previousMeetings(empty)} (each *TeamStandings: teamId, sport, stats,
  statValues, win/loss/tie counts by home/away/spread/last-ten,
  additionalStats[{label,display}]), previousYearGame (null pregame)

GET /players/sport/nfl/search?query=a&searchType=ratingLineup
  (200, 11202 bytes)
  top-level: players[]
  players[]: id, nbaId(null), sport, firstName, lastName, avatar, teamId,
  internationalTeamId, injuryStatus, jersey, birthDate, position,
  primaryRanking, alltimeRanking, overallRank, deletedAt, isTemp,
  rankings{primaryRanking, alltimeRanking}, sportRadarId, displayName,
  hasInjuryInfo, team{avatar, key}, multiplierBonus, details

Confirmed: `day` param was NOT sent in the search probe above and the
endpoint still returned 200 with results — matching WNBA's documented
behavior that `search` ignores/doesn't require `day`. Not a rigorous test of
whether `day` is *accepted* (it wasn't passed at all here), but consistent
with the WNBA precedent.

D. CONTEST IDENTITIES OBSERVED
---------------------------------
- gameId 19457 confirmed live: Seahawks (home, teamId 30, SEA) vs Patriots
  (away, teamId 21, NE), 2026-09-10T00:20:00Z, week 1, regularseason 2026,
  status "scheduled", pointSpread -4.5, overUnder 45, channel "NBC/P".
- No NFL playerratingcontest exists yet (checked ids 2120-2144 live). The
  contest id space is global across sports, created daily:
    2120  mlb    2026-08-31
    2121  mlb    2026-09-01
    2122  mlb    2026-09-02
    2123  mlb    2026-09-03
    2124  soccer 2026-09-03
    2125  ncaaf  2026-09-03
    2126-2144  403 "Not a valid contest" (not yet created)
  No nfl-sport contest has been created as of this scan. Expect one to
  appear closer to 2026-09-09 (NFL Week 1). The playerratingcontest schema
  itself (from the mlb/soccer/ncaaf ids above, since NFL's own doesn't exist
  yet) is: info.contest{id, day, sport, numBrawlers, isFinalized,
  additionalInfo{lineupSize}, createdAt, processedAt, postId, season,
  endDay, commentCount, gameId}, info.rankDisplayInfos (null pregame),
  info.nonce ("0_pregame" observed), info.completedText, info.displayText,
  info.headerText ("Draft"), info.streakDisplay, info.canEnter (true),
  info.permissionMessage (null), info.isLocked (false), info.userId,
  info.showStatsButton, lineup (empty array pregame).
- Pregame, /draftinfo and /payoutinfo both 403 "Not a valid contest" even
  for an existing (soccer, contest 2124) pregame contest — i.e. those two
  sub-routes are gated by more than just contest existence; likely
  lock/finalization state, not sport. This directly informs section J.
- Contest meta includes an info.userId field scoped to the calling session's
  own identity (not printed here per the no-operator-ID constraint); it is
  not a general user-lookup mechanism.

E. NFL PLAYER POOL CONTRACT
------------------------------
VERIFIED LIVE for the base search shape (see section C). One live sample
player from /players/sport/nfl/search: De'Von Achane (id 24179, RB, teamId
19/MIA, primaryRanking 8, alltimeRanking 831, multiplierBonus 0). Also live
in the game-feed players[] array: Jaxon Smith-Njigba (id 23157, WR, teamId
30/SEA, primaryRanking 9, primaryValue ~72.05, secondaryValue ~8.74).

Confirms two distinct player-object shapes exist depending on endpoint:
search results carry overallRank/multiplierBonus/hasInjuryInfo/birthDate;
game-feed players carry rankings.primaryValue/secondaryValue/tertiaryValue/
quaternaryValue plus a nested full team{} object. Treat these as separate
contracts, not one canonical Player type, when building a schema.

Still unverified: whether NFL's search endpoint *accepts and honors* the
other bundle-listed params (position, teamId, gameId, pollId, day, contestId,
gameIds, season, includeNoOneOption) — this probe only exercised query and
searchType. WNBA precedent (repo comment, realsports.py:353) explicitly
notes WNBA's search endpoint does NOT accept a `day` param despite it being
in the generic bundle schema; per-sport parameter support is known to
diverge from the bundle's generic schema, so do not assume NFL supports
every listed param without testing each one.

F. NFL BOOST / VALUE / SLOT CONTRACT
----------------------------------------
VERIFIED LIVE, but currently empty/pregame: GET /home/nfl/boostcontrol?
cohort=0 returned {"header":"Today's players","userPasses":[],
"shouldUpsell":true,"numMore":0}. userPasses is empty and shouldUpsell is
true, consistent with no live/active NFL slate today (next slate is
2026-09-09). Field names confirmed live match the bundle-derived list
exactly (header, userPasses, shouldUpsell, numMore) — no new/missing fields.
Value/boost content itself (what a populated userPasses entry looks like)
remains unverified — needs a re-probe on or near 2026-09-09.

Game-feed also carries a `boostInfo` key (see section C,
/games/19457/sport/nfl/feed) not previously listed in the bundle scan;
its internal shape wasn't inspected this session — flagged as new in
section O.

G. NFL FIELD / LEADERBOARD CONTRACT
---------------------------------------
/games/{gameId}/sport/nfl/stats VERIFIED LIVE for gameId 19457 (pregame,
mostly empty — see full body in section C). Confirmed field names:
playerBoxScores, gameBoxScore (periods[], teamBoxScores), stats
(numTimeoutsTotal, onFieldAmount), gameTeamComparison (homeTeamStandings,
awayTeamStandings, previousMeetings), previousYearGame. Bundle had also
claimed `metadata`, `hasMorePlayerBoxScores`, `leaderboard`, and `cutLine` on
this endpoint — none of those four keys were present in the live pregame
body. Either they are added post-game/post-lock only, or the bundle's
generic schema over-lists keys not used by every sport/state — unresolved,
flagged in section O.

/games/{gameId}/sport/{sport}/leaderboard itself (a separate route from
/stats) was NOT probed this session — still bundle-derived only, unverified
live.

H. NFL PAYOUT AND RULE CONTRACT
-----------------------------------
VERIFIED LIVE, but not for NFL (no NFL contest exists yet — see section D):
GET /games/playerratingcontest/2124/payoutinfo (contest 2124 is sport
"soccer", pregame, not finalized) returned 403 {"statusCode":403,
"error":"Forbidden","message":"Not a valid contest"}. Same 403 for
/draftinfo on the same contest. This means payoutinfo/draftinfo are gated
by something beyond "contest exists and is pregame" — likely requires the
contest to have actually locked/started, or requires the caller to have an
active lineup/entry in it. Neither hypothesis is confirmed; needs a retest
against a contest the session has actually entered, or one that has locked.
No NFL-specific payout body has been observed — this is the one section
where NFL-vs-other-sport equivalence is weakest, since the gating condition
itself is still unknown, not just the NFL instance of it.

I. HISTORICAL RECOVERABILITY MATRIX
---------------------------------------
Partially verified this session, not NFL-specific. Live evidence: contest
ids below the current frontier (2120-2125, days 2026-08-31 through
2026-09-03, all still isFinalized:false) return 200 on the base
/games/playerratingcontest/{id} route even though their day has technically
passed (today is 2026-09-02, so 2120's day 2026-08-31 is 2 days old) — so at
least the base contest-meta route stays reachable well past its own day,
contradicting a naive "expires same-day" assumption. /draftinfo and
/payoutinfo, however, 403 on 2124 (soccer, still pregame) — so reachability
differs by sub-route, not just by age. Ids above the frontier (2126-2144)
403 uniformly ("not a valid contest"), i.e. contests that don't exist yet
behave identically (403) to whatever gate blocks /draftinfo and
/payoutinfo — can't yet distinguish "doesn't exist" from "exists but
access-gated" purely from the 403 body. WNBA precedent (contest_stats.py)
explicitly separates these cases (404 vs 403) at the code level, so Real
Sports' API likely does distinguish them elsewhere; this session's probes
only exercised /draftinfo and /payoutinfo, which both returned 403 with the
same message for what are probably two different underlying conditions.
NFL-specific historical windows remain untested — no NFL contest has existed
yet to test against.

J. PRE-LOCK CAPTURE REQUIREMENTS
------------------------------------
Partially verified, not NFL-specific (no NFL contest exists yet). Live
contest 2124 (soccer) pregame meta confirms real values for the previously
name-only gating fields: isFinalized=false, isLocked=false, canEnter=true,
permissionMessage=null, nonce="0_pregame", rankDisplayInfos=null,
lineup=[] (empty pregame), additionalInfo.lineupSize=5. Despite isLocked
being false and canEnter true, /draftinfo and /payoutinfo still 403'd — so
"pregame and enterable" is NOT sufficient to unlock those two sub-routes.
The actual gating condition is still unresolved (see section H) — could be
tied to whether the *calling session* has entered the contest, a server-side
feature flag, or a lock state not reflected in the base contest-meta
response at all. Concretely, for NFL specifically: capture plans should
budget for /draftinfo and /payoutinfo potentially being unreachable via a
plain read-only session even pregame, and should test entering a contest (if
that's in scope) before concluding those endpoints are broken.

K. WNBA VERSUS NFL
----------------------
Confirmed shared platform architecture:
- Same API host (web.realapp.com) and same site host (realsports.io),
  same sport-parameterized route templates.
- Same contest primitive: playerratingcontest, same sub-route family
  (/stats, /draftinfo, /payoutinfo, /view/{userId}, /lineup).
- Same auth model (see below) applies to both — no sport-specific auth
  branch found in the WNBA code, and nothing in the bundle suggests one for
  NFL.

Confirmed differences:
- NFL adds a /timesegments PUT and a /livefeed/all/feed GET observed live
  on the NFL page that were not called out in the WNBA ingest code reviewed
  in this repo — likely feature additions or app-shell calls not
  WNBA-specific, unconfirmed.
- WNBA's /players/sport/{sport}/search omits the `day` param despite it
  being in the generic bundle schema (explicit repo comment). The NFL search
  probe this session succeeded without passing `day` at all, consistent with
  (but not a strict test of) the same behavior.
- The playerratingcontest id space is confirmed global/shared across sports
  (2120-2123 mlb, 2124 soccer, 2125 ncaaf, all created 2026-08-31 through
  2026-09-03), not per-sport. This wasn't visible from the WNBA-only code
  and is a genuinely new finding this session, applicable to NFL too: expect
  NFL's first contest id to simply be the next integer once one is created,
  not some NFL-specific numbering.

L. OBSERVED FACTS VERSUS HYPOTHESES
---------------------------------------
Observed (live, this platform, NFL context, this session unless noted):
- The 6 endpoint calls under section B "VERIFIED LIVE" — full response
  bodies now captured (section C), not just request URLs (prior session)
- Route https://realsports.io/n8gT1tOFAM2 (prior session)
- gameId 19457 full game object: SEA vs NE, 2026-09-10T00:20:00Z, spread
  -4.5, O/U 45 (this session)
- Page text sections: "Games", "On this week (plays)", "On this week
  (performances)" (prior session)
- No NFL playerratingcontest exists as of 2026-09-02; contest id space is
  global across sports and sequential by creation day (this session)
- /draftinfo and /payoutinfo 403 on an existing pregame non-NFL contest
  (this session)

Bundle-derived (real code, not sport-specific execution):
- Paths/params in section B's "BUNDLE-DERIVED" list not otherwise now
  confirmed live in section C
- The metadata/hasMorePlayerBoxScores/leaderboard/cutLine fields claimed for
  /stats but absent from the live pregame body (see section G)

WNBA precedent (real, verified, but a different sport):
- BASE host, header names, auth flow, all endpoints in section B's "WNBA
  PRECEDENT" list, 401/404/403/429 error-handling semantics in
  contest_stats.py

Still hypothesis / unresolved (no direct evidence either way):
- The actual gating condition for /draftinfo and /payoutinfo 403s (session
  entry state vs lock state vs feature flag) — section H, J
- Whether a live/entered NFL contest changes those two routes' behavior
- Distinction between "contest doesn't exist" 403 and "exists but
  access-gated" 403 — both currently look identical
- NFL-specific historical/expiry windows (no NFL contest has existed yet)
- Whether NFL /search honors params beyond query/searchType
- Whether NFL exposes a distinct /entries endpoint (WNBA has one; not
  independently probed for NFL this session since no NFL contest exists)

M. ANOMALIES AND WARNINGS
-----------------------------
- The playerratingcontest bundle route list for NFL does not include
  /entries, which IS present and load-bearing in the live WNBA code. This
  could mean NFL genuinely lacks a leaderboard-entries endpoint, or it could
  mean the bundle read was incomplete. Flagged, not resolved.
- Chrome extension connectivity was unreliable across two consecutive
  sessions (flaky CDP in the prior session, fully disconnected in this one).
  Any capture plan should not assume the browser automation path is
  reliably available; a manual HAR export or a scripted httpx/Playwright
  probe (mirroring probe_realsports.py's pattern) is more robust than
  live browser-tool network capture for this task.

N. MINIMUM NFL RAW CAPTURE CONTRACT
---------------------------------------
To close the gaps in this report, capture (as raw response bodies, not
summaries) at minimum:
1. GET /home/nfl/next?cohort=0
2. GET /home/nfl/boostcontrol?cohort=0&day=<current slate day>
3. GET /squads?sport=nfl
4. GET /games/{gameId}/sport/nfl/feed?version=2&view=recent&viewFrame=default
5. GET /games/{gameId}/sport/nfl/stats
6. GET /games/playerratingcontest/{contestId}
7. GET /games/playerratingcontest/{contestId}/draftinfo
8. GET /games/playerratingcontest/{contestId}/stats
9. GET /games/playerratingcontest/{contestId}/payoutinfo (post-payout, on an
   already-settled contest, to see final shape)
10. GET /players/sport/nfl/search?query=a&searchType=ratingLineup (mirroring
    the WNBA probe script's exact call) — specifically to test whether `day`
    is accepted/ignored for NFL

O. OPEN QUESTIONS
---------------------
- Does NFL's contest surface include /entries like WNBA's does?
- Does /players/sport/nfl/search accept and honor `day`, given NFL's
  day-keyed slate structure?
- What triggers a contest to move from live to "historical" (403/404) on
  NFL, and how long is the historical window compared to WNBA?
- Is the API host for NFL calls actually web.realapp.com, matching WNBA,
  or does the live browser session route NFL calls elsewhere? (Not
  independently re-confirmed this session.)
- What does /timesegments actually control, and is it NFL-specific or a
  general app-shell call also fired on WNBA pages that simply wasn't
  captured in the WNBA ingest code (which targets specific endpoints, not
  a full page-load trace)?

P. COPY-PASTE HANDOFF FOR CHATGPT
-------------------------------------
Continue Real Sports NFL endpoint archaeology in github.com/cheeksmagunda/sports.

State: Two sessions have now attempted live NFL response-body capture via
Claude-in-Chrome browser automation. First session: CDP/websocket attach was
flaky, captured request URLs but no bodies. Second session (this one): the
Chrome extension was not connected at all (no browser tools available),
so no new data — the task fell back to writing up findings only.

Repo files were not modified in either session.

VERIFIED LIVE NFL request families (bodies never captured):
- PUT /timesegments  body {"timeSegments":1}
- GET /home/nfl/next?cohort=0
- GET /home/nfl/boostcontrol?cohort=0&day=2026-09-09
- GET /squads?sport=nfl
- GET /livefeed/all/feed
- GET /games/19457/sport/nfl/feed?version=2&view=recent&viewFrame=default
Live route: https://realsports.io/n8gT1tOFAM2

BUNDLE-DERIVED NFL paths (names only, unverified live):
/home/{sport}/days, /home/{sport}/day/next, /home/{sport}/boostcontrol,
/home/loginslate, /players/sport/{sport}/search, /players/sport/{sport}/compare,
/players/embedinfo/{playerId}/sport/{sport}, /games/{gameId}/sport/{sport}/feed,
/games/{gameId}/sport/{sport}/stats, /games/{gameId}/sport/{sport}/position-graph,
/games/{gameId}/sport/{sport}/compete, /games/{gameId}/sport/{sport}/leaderboard,
/games/{gameId}/sport/{sport}/checkins, /games/{gameId}/sport/{sport}/light,
/games/playerratingcontest/{contestId}[/view/{userId}|/draftinfo|/stats|/payoutinfo],
PUT /games/playerratingcontest/{contestId}/lineup

WNBA precedent worth reusing directly (from wnba-oracle/src/wnba_oracle/ingest/
realsports.py + contest_stats.py + scripts/probe_realsports.py +
scripts/probe_leaderboard.py):
- BASE = https://web.realapp.com; site = https://realsports.io
- Auth: operator-seeded Playwright session -> storage_state.json, harvest
  `real-request-token` + `real-auth-info` headers from authenticated
  requests, cache 30 min (request_token_cache.json). 401 -> refresh once.
- WNBA's /players/sport/{sport}/search does NOT accept `day` despite it
  appearing in the generic bundle param schema — check this for NFL first,
  it's the cheapest high-value probe.
- WNBA has a confirmed /games/playerratingcontest/{id}/entries endpoint not
  seen in the NFL bundle scan — open question whether NFL has an equivalent.
- Historical/expired contests 403 or 404 on /stats and /entries in WNBA
  (contest_stats.py explicit handling) — untested for NFL.

Recommended next action: don't rely on live browser-tool network capture
alone (it has failed twice). Prefer a scripted probe mirroring
probe_realsports.py/probe_leaderboard.py against an NFL contest id and
gameId 19457, using a freshly captured storage_state.json for an NFL-viewing
session, and write raw JSON to fixtures for offline schema analysis. Then
fill in sections C, D, E, F, G, H, I, J of the archaeology report with real
field values.

No secrets, cookies, tokens, or operator identifiers are included in this
report.

Q. SCHEMA SNAPSHOT
-------------------
Captured from `drive/nfl_fixtures/*.json`, the live NFL bodies are JSON
objects with different leaf contracts by route:

- `/home/nfl/next?cohort=0`:
  - root: `days: array<object>`, `cohortOptions: null`, `latestDay: string`,
    `latestDayContent: object`, `latestWeek: string`, `liveGameInfo: bool`,
    `emojiUsages: array<empty>`
  - `days[0]`: `index:int`, `dateTime:string`, `day:string`, `week:int`,
    `weekNum:int`, `count:string`, `pos:null`, `detail:string`
  - `latestDayContent`: `day:string`, `week:int`, `season:int`,
    `games: array<object>`, `replayGames: array<empty>`, `replayConfig: object`,
    `config: object`, `upsellInfo:null`, `items: array<object>`,
    `groupToGameIds:null`, `gamesHeader:null`, `headerSource:null`
  - `latestDayContent.config`: `showStandings: bool`, `showBoostControl: bool`,
    `dailyDraftInfo:null`, `standingsConference:null`,
    `groupViewMoreText:null`

- `/home/nfl/boostcontrol?cohort=0`:
  - `header:string`, `userPasses: array<empty>`, `shouldUpsell: bool`,
    `numMore: int`

- `/squads?sport=nfl`:
  - `statTrackerInfo`: `header:string`, `description:string`,
    `latestDay:string`, `statTrackerGroups: array<empty>`
  - `squads: array<empty>`

- `/games/19457/sport/nfl/feed?version=2&view=recent&viewFrame=default`:
  - root: `game: object`, `matchPlayerBoxScores: null`, `eventInfo: null`,
    `plays: array<empty>`, `posts: array<empty>`, `players: array<object>`,
    `upsellInfo: null`, `upsellPacks: bool`, `alertMessage: null`,
    `inviteUpsell: null`, `market: null`, `hasMarket: bool`,
    `liveActivityEnabled: bool`, `messageChannelId: null`,
    `ignoreEmojiUsages: bool`, `alwysShowValue: number`, `numLatestPlays: int`,
    `ignoreGameData: bool`, `boxScoreCategoryTabs: array<object>`,
    `boostInfo: object`, `upsellReferrals: bool`,
    `availableGameFeedViews: array<object>`, `defaultGameTab: null`
  - `game`: full slate game object with mostly scalar fields plus nested
    `display`, `situationalInsights`, `homeTeam`, and `awayTeam`
  - `players[0]`: `id:int`, `sport:string`, `teamId:int`, `avatar:string`,
    `firstName:string`, `lastName:string`, `jersey:string`, `position:string`,
    `injuryStatus:string`, `injuryBodyPart:null`, `gameId:int`,
    `rankings: object`, `seasonAverages: object`, `primaryRanking:int`,
    `details: object`, `backgroundColor:string`, `team: object`
  - `players[0].rankings`: `playerId:int`, `sport:string`,
    `primaryRanking:int`, `secondaryRanking:int`, `tertiaryRanking:int`,
    `quaternaryRanking:int`, `previousPrimary:int`, `previousSecondary:int`,
    `previousTertiary:int`, `previousQuaternary:int`, `primaryValue:number`,
    `secondaryValue:number`, `tertiaryValue:number`, `quaternaryValue:number`,
    `alltimeRanking:int`, `alltimeValue:number`, `previousAlltime:number`
  - `boostInfo`: `canBoost: bool`, `brawlEnabled: bool`

- `/games/19457/sport/nfl/stats`:
  - root: `playerBoxScores: array<empty>`, `gameBoxScore: object`,
    `stats: object`, `gameTeamComparison: object`, `previousYearGame: null`
  - `gameBoxScore.periods[0]`: `sequence:int`, `homeTeamScore:int`,
    `awayTeamScore:int`, `label:string`
  - `stats`: `numTimeoutsTotal:int`, `onFieldAmount:null`
  - `gameTeamComparison`: `homeTeamStandings: object`,
    `awayTeamStandings: object`, `previousMeetings: array<empty>`

- `/players/sport/nfl/search?query=a&searchType=ratingLineup`:
  - root: `players: array<object>`
  - `players[0]`: `id:int`, `nbaId:null`, `sport:string`, `firstName:string`,
    `lastName:string`, `avatar:string`, `teamId:int`,
    `internationalTeamId:null`, `injuryStatus:string`, `jersey:string`,
    `birthDate:string`, `position:string`, `primaryRanking:int`,
    `alltimeRanking:int`, `overallRank:int`, `deletedAt:null`, `isTemp:bool`,
    `rankings: object`, `sportRadarId:string`, `displayName:string`,
    `hasInjuryInfo:bool`, `team: object`, `multiplierBonus:int`,
    `details: object`

- `/games/playerratingcontest/2124`:
  - `info.contest`: `id:int`, `day:string`, `sport:string`,
    `numBrawlers:int`, `isFinalized:bool`, `additionalInfo: object`,
    `createdAt:string`, `processedAt:null`, `postId:int`, `season:int`,
    `endDay:string`, `commentCount:int`, `gameId:null`
  - `info.contest.additionalInfo`: `lineupSize:int`
  - `info`: `rankDisplayInfos:null`, `nonce:string`, `completedText:null`,
    `displayText:null`, `headerText:string`, `streakDisplay:null`,
    `canEnter:bool`, `permissionMessage:null`, `isLocked:bool`,
    `userId:string`, `showStatsButton:bool`
  - `lineup: array<empty>`

- `/games/playerratingcontest/2124/stats`:
  - `displayInfo`: `title:string`, `emptyStateText:string`, `details:string`
  - `contest`: same core contest object shape as above
  - `draftStats: array<empty>`

- `/games/playerratingcontest/2124/draftinfo` and `/payoutinfo`:
  - same error envelope: `statusCode:int`, `error:string`, `message:string`
