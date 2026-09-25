# Status


## Landed (#330, 2026-09-25 ~17:52 CT)
<!-- merged-330-e3fba499 -->
- Squash-merged measured boost-aware picker knobs (Corpus C identity 51.7% -> boost_0.75 57.9%).
- Railway intended: `NFL_PICKER_BOOST_RANK_BLEND=0.75`, `NFL_PICKER_PROFILE=boost_0.75` on worker+API.
- Defaults in code remain identity; live profile is env-driven.
- FULL RESTORE IN PROGRESS (placeholder; next commit restores 107KB body).
