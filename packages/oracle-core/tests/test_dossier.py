from __future__ import annotations

import pytest

from oracle_core.dossier import (
    ORACLE_VOCAB,
    Achievability,
    DataQualityAndCensoring,
    FeasibilityConstraint,
    FeasibleActionFamily,
    GapMetric,
    KnowledgeState,
    LearningSummary,
    ProvenanceStatus,
    RealizedOutcomes,
    SlateDossier,
    SlateEntry,
    SlateIdentity,
    SlotSelection,
    build_gap_analysis,
    gap_metric_from_entries,
)


def _slots(*players: tuple[str, str]) -> tuple[SlotSelection, ...]:
    return tuple(
        SlotSelection(
            position=index,
            slot_id=f"slot_{index}",
            participant_id=player_id,
            participant_name=name,
            team_id=f"T{index}",
            team_name=f"Team {index}",
        )
        for index, (player_id, name) in enumerate(players, start=1)
    )


def _entry(
    achievability: Achievability,
    score: float | None,
    *,
    provenance: ProvenanceStatus = ProvenanceStatus.EXACT,
    payout: float | None = None,
    slots: tuple[SlotSelection, ...] | None = None,
    label: str | None = None,
) -> SlateEntry:
    return SlateEntry(
        achievability=achievability,
        slots=slots or _slots(("p1", "Player 1"), ("p2", "Player 2"), ("p3", "Player 3")),
        label=label,
        realized_score=score,
        realized_payout=payout,
        provenance=provenance,
        slot_order_basis="committed_slot_order",
    )


def _sample_dossier() -> SlateDossier:
    family = FeasibleActionFamily(
        ordered_slots=("slot_1", "slot_2", "slot_3"),
        constraints=(
            FeasibilityConstraint(name="max_from_one_team", value=2, operator="<="),
            FeasibilityConstraint(name="ordered_slots_required", value=True),
        ),
        max_from_one_group=2,
        summary="Three-slot example proving variable K support.",
    )
    our_entry = _entry(
        Achievability.OUR_COMMITTED,
        88.2,
        payout=12.5,
        label="Our committed entry",
    )
    field_entry = _entry(
        Achievability.OBSERVED_FIELD,
        93.4,
        payout=35.0,
        label="Observed field winner",
    )
    theoretical_entry = _entry(
        Achievability.THEORETICAL_HINDSIGHT_UPPER_BOUND,
        97.0,
        label="Theoretical ceiling",
    )
    return SlateDossier(
        slate_identity=SlateIdentity(
            slate_id="slate-2026-08-30-top20",
            contest_id="contest-123",
            slate_date="2026-08-30",
            sport="Basketball",
            contest_name="Daily contest",
            league="WNBA",
        ),
        knowledge_state=KnowledgeState(
            as_of="2026-08-30T18:55:00Z",
            decision_cutoff_at="2026-08-30T19:00:00Z",
            artifact_id="model:picker-20260830",
            artifact_version="sha256:abc123",
            notes=("pre-lock snapshot", "inputs frozen"),
        ),
        feasible_action_family=family,
        our_committed_entry=our_entry,
        best_observed_field_entry=field_entry,
        theoretical_best_entry=theoretical_entry,
        gap_analysis=build_gap_analysis(our_entry, field_entry, theoretical_entry),
        realized_outcomes=RealizedOutcomes(
            settled=True,
            settled_at="2026-08-31T09:00:00Z",
            field_size=6800,
            cash_line_score=90.5,
            our_rank=41,
            our_percentile=0.994,
            notes=("contest settled",),
        ),
        data_quality_and_censoring=DataQualityAndCensoring(
            provenance=ProvenanceStatus.EXACT,
            leaderboard_capture_depth=100,
            observed_entry_count=6800,
            note="Complete leaderboard and labels available.",
        ),
        learning_summary=LearningSummary(
            summary="Our committed lineup was competitive but left points on the table.",
            takeaways=("field winner captured more ceiling",),
            follow_ups=("review late-swap heuristics",),
        ),
    )


def test_build_gap_analysis_calculates_required_metrics() -> None:
    dossier = _sample_dossier()

    gaps = dossier.gap_analysis
    assert gaps.our_to_field_winner_score_gap.name == "our_to_field_winner_score_gap"
    assert gaps.our_to_field_winner_score_gap.value == pytest.approx(5.2)
    assert gaps.field_winner_to_theoretical_ceiling_gap.value == pytest.approx(3.6)
    assert gaps.our_to_theoretical_ceiling_gap.value == pytest.approx(8.8)
    assert gaps.our_to_field_winner_score_gap.provenance is ProvenanceStatus.EXACT


def test_gap_helper_preserves_censored_and_unavailable_semantics() -> None:
    our_entry = _entry(
        Achievability.OUR_COMMITTED,
        82.0,
        provenance=ProvenanceStatus.CENSORED,
    )
    field_entry = _entry(Achievability.OBSERVED_FIELD, 90.0)
    ceiling_entry = _entry(
        Achievability.THEORETICAL_HINDSIGHT_UPPER_BOUND,
        None,
        provenance=ProvenanceStatus.UNAVAILABLE,
    )

    censored_gap = gap_metric_from_entries(
        "our_to_field_winner_score_gap",
        our_entry,
        field_entry,
    )
    unavailable_gap = gap_metric_from_entries(
        "our_to_theoretical_ceiling_gap",
        our_entry,
        ceiling_entry,
    )

    assert censored_gap.value == pytest.approx(8.0)
    assert censored_gap.provenance is ProvenanceStatus.CENSORED
    assert unavailable_gap.value is None
    assert unavailable_gap.provenance is ProvenanceStatus.UNAVAILABLE


def test_slate_dossier_requires_three_distinct_first_class_entry_kinds() -> None:
    family = FeasibleActionFamily(ordered_slots=("slot_1", "slot_2", "slot_3"))
    our_entry = _entry(Achievability.OUR_COMMITTED, 80.0)
    wrong_field = _entry(Achievability.OUR_COMMITTED, 90.0)
    theoretical = _entry(Achievability.THEORETICAL_HINDSIGHT_UPPER_BOUND, 95.0)

    with pytest.raises(ValueError, match="best_observed_field_entry"):
        SlateDossier(
            slate_identity=SlateIdentity("slate-1", "contest-1", "2026-08-30"),
            knowledge_state=KnowledgeState(as_of="2026-08-30T18:00:00Z"),
            feasible_action_family=family,
            our_committed_entry=our_entry,
            best_observed_field_entry=wrong_field,
            theoretical_best_entry=theoretical,
            gap_analysis=build_gap_analysis(our_entry, wrong_field, theoretical),
            realized_outcomes=RealizedOutcomes(),
            data_quality_and_censoring=DataQualityAndCensoring(provenance=ProvenanceStatus.PARTIAL),
            learning_summary=LearningSummary(),
        )


def test_slate_dossier_enforces_committed_slot_order_for_all_entries() -> None:
    family = FeasibleActionFamily(ordered_slots=("slot_1", "slot_2", "slot_3"))
    our_entry = _entry(Achievability.OUR_COMMITTED, 80.0)
    field_entry = _entry(Achievability.OBSERVED_FIELD, 90.0)
    misordered_theoretical = SlateEntry(
        achievability=Achievability.THEORETICAL_HINDSIGHT_UPPER_BOUND,
        slots=(
            SlotSelection(1, "slot_2", "p2"),
            SlotSelection(2, "slot_1", "p1"),
            SlotSelection(3, "slot_3", "p3"),
        ),
        realized_score=95.0,
    )

    with pytest.raises(ValueError, match="committed slot order"):
        SlateDossier(
            slate_identity=SlateIdentity("slate-1", "contest-1", "2026-08-30"),
            knowledge_state=KnowledgeState(as_of="2026-08-30T18:00:00Z"),
            feasible_action_family=family,
            our_committed_entry=our_entry,
            best_observed_field_entry=field_entry,
            theoretical_best_entry=misordered_theoretical,
            gap_analysis=build_gap_analysis(our_entry, field_entry, misordered_theoretical),
            realized_outcomes=RealizedOutcomes(),
            data_quality_and_censoring=DataQualityAndCensoring(provenance=ProvenanceStatus.PARTIAL),
            learning_summary=LearningSummary(),
        )


def test_jsonld_round_trip_preserves_schema_and_custom_semantics() -> None:
    dossier = _sample_dossier()

    document = dossier.to_jsonld()
    restored = SlateDossier.from_jsonld(document)

    assert document["@context"]["oracle"] == ORACLE_VOCAB
    assert document["@type"] == "CreativeWork"
    assert document["additionalType"] == f"{ORACLE_VOCAB}SlateDossier"
    assert document["oracle:ourCommittedEntry"]["@type"] == "ItemList"
    assert document["oracle:gapAnalysis"]["oracle:ourToFieldWinnerScoreGap"]["@type"] == (
        "Observation"
    )
    assert restored == dossier


def test_variable_k_is_not_hardcoded_to_five_slots() -> None:
    slots = _slots(
        ("p1", "Player 1"),
        ("p2", "Player 2"),
        ("p3", "Player 3"),
        ("p4", "Player 4"),
        ("p5", "Player 5"),
        ("p6", "Player 6"),
    )
    family = FeasibleActionFamily(
        ordered_slots=tuple(slot.slot_id for slot in slots),
        max_from_one_group=3,
    )
    our_entry = _entry(Achievability.OUR_COMMITTED, 120.0, slots=slots)
    field_entry = _entry(Achievability.OBSERVED_FIELD, 124.0, slots=slots)
    theoretical_entry = _entry(
        Achievability.THEORETICAL_HINDSIGHT_UPPER_BOUND,
        130.0,
        provenance=ProvenanceStatus.PARTIAL,
        slots=slots,
    )
    dossier = SlateDossier(
        slate_identity=SlateIdentity("slate-6", "contest-6", "2026-09-01"),
        knowledge_state=KnowledgeState(as_of="2026-09-01T18:00:00Z"),
        feasible_action_family=family,
        our_committed_entry=our_entry,
        best_observed_field_entry=field_entry,
        theoretical_best_entry=theoretical_entry,
        gap_analysis=build_gap_analysis(our_entry, field_entry, theoretical_entry),
        realized_outcomes=RealizedOutcomes(settled=False),
        data_quality_and_censoring=DataQualityAndCensoring(
            provenance=ProvenanceStatus.PARTIAL,
            censoring_reasons=("awaiting_final_box_score",),
        ),
        learning_summary=LearningSummary(),
    )

    assert dossier.feasible_action_family.entry_size == 6
    assert dossier.our_committed_entry.ordered_slots[-1].slot_id == "slot_6"
    assert (
        dossier.gap_analysis.our_to_theoretical_ceiling_gap.provenance is ProvenanceStatus.PARTIAL
    )


def test_round_trip_dict_preserves_missing_and_censored_outcomes() -> None:
    dossier = _sample_dossier()
    dossier = SlateDossier(
        slate_identity=dossier.slate_identity,
        knowledge_state=dossier.knowledge_state,
        feasible_action_family=dossier.feasible_action_family,
        our_committed_entry=dossier.our_committed_entry,
        best_observed_field_entry=dossier.best_observed_field_entry,
        theoretical_best_entry=SlateEntry(
            achievability=Achievability.THEORETICAL_HINDSIGHT_UPPER_BOUND,
            slots=dossier.theoretical_best_entry.slots,
            provenance=ProvenanceStatus.CENSORED,
            censoring_reason="leaderboard truncated before all paid places",
        ),
        gap_analysis=build_gap_analysis(
            dossier.our_committed_entry,
            dossier.best_observed_field_entry,
            SlateEntry(
                achievability=Achievability.THEORETICAL_HINDSIGHT_UPPER_BOUND,
                slots=dossier.theoretical_best_entry.slots,
                provenance=ProvenanceStatus.UNAVAILABLE,
            ),
        ),
        realized_outcomes=RealizedOutcomes(
            settled=None,
            notes=("final results unavailable",),
        ),
        data_quality_and_censoring=DataQualityAndCensoring(
            provenance=ProvenanceStatus.CENSORED,
            missing_sources=("final leaderboard export",),
            censoring_reasons=("provider exported only top-100",),
        ),
        learning_summary=dossier.learning_summary,
    )

    restored = SlateDossier.from_dict(dossier.to_dict())

    assert restored.realized_outcomes.settled is None
    assert restored.theoretical_best_entry.realized_score is None
    assert restored.theoretical_best_entry.provenance is ProvenanceStatus.CENSORED
    assert (
        restored.gap_analysis.our_to_theoretical_ceiling_gap.provenance
        is ProvenanceStatus.UNAVAILABLE
    )
    assert restored.data_quality_and_censoring.missing_sources == ("final leaderboard export",)


def test_gap_metric_rejects_unavailable_numeric_value() -> None:
    with pytest.raises(ValueError, match="Unavailable gap metrics"):
        GapMetric(
            name="our_to_theoretical_ceiling_gap",
            value=1.0,
            provenance=ProvenanceStatus.UNAVAILABLE,
        )
