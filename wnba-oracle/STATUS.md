# Status

Last verified: 2026-09-25T22:25:00Z

This file records live operational state only. Values marked unverified were
not exposed by the read-only checks available during this audit.

## rotowire_empty + enrichment_stale (#319)  -  2026-09-25

- **After deploy (2026-09-25 ~5:22 PM CT):** merge `392e5af` / PR #323 live on
  `api` deploy `3f3b74bf` then `184a3086`. `/watchdog/today` returns
  `status=ok`, `events=[]`. Prior `rotowire_empty` / `enrichment_stale` rows
  remain under `history` only (forensics). Tip-aware gates + live-eval landed.
- **Follow-up:** live-eval also surfaced `model_artifact_unset` on `api`
  (cron-job2 already had `WNBA_ORACLE_MODEL_ARTIFACT_SHA`). Set API to the
  Actions `WNBA_EXPECTED_MODEL_SHA` /
  `picker_95264ce9_1788339935` artifact
  `7b06b6f98d0bb0cd69d4b12c49c5c97102b39eb30734c586f9d1f02ab69f1da2`
  (audit hash `2e894c6c`). Redeploy `184a3086` cleared the critical.
- **Leverage:** keep `0.28`; Railway `cron-job2` `OPTIMIZER_LEVERAGE_WEIGHT`
  unchanged. No picker-knob flip from leak-free default grid (#317 / #322).

PLACEHOLDER_REST_OF_FILE
