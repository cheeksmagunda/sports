# coverage_manifest offline status (#526)

- Mode: `offline_fixture_dry_run` (no Ollama, no Real Sports network)
- `historical_capture_complete`: **False**
- Ollama Codespace helper: **FORBIDDEN**
- Fixture family cells present: 13/44

## Sibling corpus (live)

As of dry-run generation: sibling repo holds kind dirs + empty coverage_manifest (all unknown) plus one synthetic NFL HV proof slate under total_value_leaderboards/nfl/2026/slate_2026-01-01/. historical_capture_complete remains false.

## COMPLETE vs MISSING (post #532/#534/#537/#538/#539/#533)

| Surface | WNBA | NFL | NBA | NHL |
|---|---|---|---|---|
| HV boards (total_value_leaderboards) | COMPLETE export path (#532/#539); MISSING sibling publish (needs CORPUS_REPO_TOKEN) | COMPLETE Corpus C offline export (#534); MISSING volume→sibling append | MISSING ingest (fail-closed stub #532) | PARTIAL HV train path (#542); MISSING RS contest corpus export |
| Corpus G (game boxes / players / feed) | MISSING RS Corpus-G-style store (game_logs partial elsewhere) | COMPLETE on Railway volume (~3k files); MISSING kind-first sibling publish | MISSING | PARTIAL official NHL history; MISSING RS boxes in sibling |
| Corpus C (contest archive) | n/a (Postgres slate_labels / contest_leaderboards) | COMPLETE offline HV+draftStats+matchups export (#534); MISSING sibling hydrate | MISSING | MISSING |
| Matchups / game-stats append | COMPLETE script path (#537); MISSING full-history sibling fill | COMPLETE Corpus G + #537 append; MISSING sibling soft-merge | COMPLETE fail-closed append stub (#537); MISSING ingest | COMPLETE append stub (#537); MISSING RS matchup history in sibling |
| draftStats all sections | COMPLETE dump CLI (#538) + Postgres export (#539); MISSING sibling publish | COMPLETE via Corpus C export (#534); MISSING sibling publish | MISSING | MISSING durable (audit-only historically) |

## Fixture dry-run family rollup

| Sport | players | team_weights | lineups | slate_rosters | averages | combined_stats | recorded_states | total_value_leaderboards | matchups | draft_stats_all_sections | feeds |
|---|---|---|---|---|---|---|---|---|---|---|---|
| wnba | present | stub | present | stub | stub | present | stub | present | stub | stub | stub |
| nfl | present | partial | present | present | stub | present | present | present | present | present | present |
| nba | stub | stub | stub | stub | stub | stub | stub | stub | stub | stub | stub |
| nhl | stub | stub | stub | stub | stub | stub | stub | stub | stub | stub | stub |

## Operator Ollama unlock checklist

1. Do NOT install or wire Ollama until historical_capture_complete is true.
2. Provision CORPUS_REPO_TOKEN (contents:write on cheeksmagunda/sports-realsports-corpus); agents must not mint.
3. Confirm REALSPORTS_STORAGE_STATE_B64GZ is injected into Codespace process env (sha256[:8] only).
4. Publish WNBA Postgres export (#539) + NFL Corpus C/G exports (#534/#537) into sibling via realsports-corpus-append workflow_dispatch confirm_append=true.
5. Fill NBA RS ingest (today fail-closed) and NHL RS contest/HV durable export beyond official history.
6. Soft-merge coverage_manifest.json until every sport×family is present with artifact_count>=1.
7. Re-read sibling coverage_manifest.json; only then set/allow Ollama Codespace helper.
