# oracle-core

`oracle-core` contains provider-neutral technical infrastructure shared by
Sports Oracle applications. It deliberately contains no league, calendar,
player, scoring, model, strategy, or provider contract.

The public package includes:

- process-environment configuration, secret-aware values, and redaction;
- structured JSON logging and safe exception rendering;
- synchronous and asynchronous HTTP transport and bounded retries;
- PostgreSQL transaction, Redis key-value, lease, and JSON cache primitives;
- registered job execution with roles, lifecycle events, clocks, and leases;
- generic FastAPI root and health behavior;
- cross-sport post-slate dossier contract and JSON-LD helpers;
- atomic artifact persistence, integrity checks, and deterministic test fakes;
- day-close sweep orchestration (`oracle_core.dayclose`): grade a target day,
  then retry a bounded catch-up window for anything still ungraded;
- schema.org / JSON-LD entity helpers (`oracle_core.schemaorg`) for Person,
  SportsTeam, SportsOrganization, SportsEvent, Place, OrganizationRole,
  identifier/PropertyValue, sameAs, Observation, QuantitativeValue, ItemList,
  plus optional PROV-O attribution; high-TV boards in `oracle_core.high_tv`.

Applications retain ownership of their settings extensions, database schema,
migrations, routes, jobs, schedules, provider adapters, and domain behavior.
`oracle_core.dayclose.run_sweep` is intentionally thin: it isolates one day's
failure from the rest of the sweep and aggregates outcomes into a
`JobResult`, but every domain judgment stays in the calling application: what
"graded" means, what provider data to refresh, and which day's identity to use
are defined by its `close_one_day` callback, while its `settled_statuses` set
defines which returned statuses are terminal rather than worth flagging.
## Dossier schema (#39)

`oracle_core.dossier.SlateDossier` defines the cross-sport post-slate dossier
contract. It composes exactly ten concepts:

- `slate_identity`
- `knowledge_state`
- `feasible_action_family`
- `our_committed_entry`
- `best_observed_field_entry`
- `theoretical_best_entry`
- `gap_analysis`
- `realized_outcomes`
- `data_quality_and_censoring`
- `learning_summary`

The contract keeps three first-class entry records distinct: the lineup we
actually froze, the best observed field lineup, and the theoretical hindsight
upper bound. Ordered entries serialize as schema.org `ItemList`/`ListItem`;
realized scores, payouts, and gap metrics serialize as schema.org
`Observation`/`QuantitativeValue`; dossier-only semantics such as
`theoretical_hindsight_upper_bound` travel in the namespaced `oracle:` JSON-LD
vocabulary.

```python
from oracle_core.dossier import (
    Achievability,
    FeasibleActionFamily,
    KnowledgeState,
    DataQualityAndCensoring,
    LearningSummary,
    ProvenanceStatus,
    RealizedOutcomes,
    SlateDossier,
    SlateEntry,
    SlateIdentity,
    SlotSelection,
    build_gap_analysis,
)

family = FeasibleActionFamily(ordered_slots=("slot_1", "slot_2", "slot_3"))
our_entry = SlateEntry(
    achievability=Achievability.OUR_COMMITTED,
    slots=(
        SlotSelection(1, "slot_1", "p1", participant_name="Player 1"),
        SlotSelection(2, "slot_2", "p2", participant_name="Player 2"),
        SlotSelection(3, "slot_3", "p3", participant_name="Player 3"),
    ),
    realized_score=88.2,
)
field_entry = SlateEntry(
    achievability=Achievability.OBSERVED_FIELD,
    slots=our_entry.slots,
    realized_score=93.4,
)
theoretical_entry = SlateEntry(
    achievability=Achievability.THEORETICAL_HINDSIGHT_UPPER_BOUND,
    slots=our_entry.slots,
    realized_score=97.0,
)

dossier = SlateDossier(
    slate_identity=SlateIdentity("slate-1", "contest-1", "2026-08-30"),
    knowledge_state=KnowledgeState(as_of="2026-08-30T18:55:00Z"),
    feasible_action_family=family,
    our_committed_entry=our_entry,
    best_observed_field_entry=field_entry,
    theoretical_best_entry=theoretical_entry,
    gap_analysis=build_gap_analysis(our_entry, field_entry, theoretical_entry),
    realized_outcomes=RealizedOutcomes(settled=True, our_rank=14),
    data_quality_and_censoring=DataQualityAndCensoring(
        provenance=ProvenanceStatus.EXACT,
    ),
    learning_summary=LearningSummary(summary="Review the remaining score gap."),
)
jsonld_document = dossier.to_jsonld()
```

