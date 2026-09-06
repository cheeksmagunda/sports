# UNKNOWN_PROVIDER_RULES — offline notes (no submit)

Best-effort public / historical notes for the seven `#91` unknown provider
rules. Source of truth in code: `nfl_oracle.providers.five_card`
(`UNKNOWN_PROVIDER_RULES`, `OFFLINE_RULE_NOTES`,
`offline_provider_rule_document()`).

**Documenting a rule does not close it.** Notes never flip
`provider_contract_verified`, never enable `submit()`, and never authorize
contest entry. See Drive `NFL-ORACLE-strategy.txt` empirical findings
2026-09-02 for the underlying observations (finalized contests only).

| Rule key | Offline status |
|----------|----------------|
| `provider_roster_and_inventory_eligibility` | Draftable pool / roster shapes observed post-settlement; pre-lock inventory gates unknown |
| `provider_duplicate_card_rules` | Structural 5-id uniqueness only; provider inventory duplicates unknown |
| `slot_weights_and_scoring` | `defaultMultipliers` [2, 1.8, 1.6, 1.4, 1.2] + non-negative algebra observed |
| `provider_lock_semantics` | No pre-lock NFL capture; lock field/proxy unverified |
| `multiplier_bonus_pre_lock_visibility` | Finalized boosts populated; pregame search zeros — live_ok=false |
| `negative_value_scoring_branch` | Non-NFL exception observed; NFL non-negative branch only |
| `submission_payload_shape` | Settlement `/entries` shape ≠ proven submit body |

Refresh notes when live contract work lands; keep keys in
`UNKNOWN_PROVIDER_RULES` until verified.
