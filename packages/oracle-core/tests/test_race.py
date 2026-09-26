from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from oracle_core.race import (
    Dimension,
    DimKind,
    EvalContext,
    Fidelity,
    FitConfig,
    FitResult,
    Racer,
    RandomSampler,
    RankObservation,
    SearchSpace,
    SlateResult,
    StopPolicy,
    Variant,
    VariantRecord,
    breed_generation,
    crossover,
    merge_shard_records,
    mutate,
    partition_variants,
    process_pool_map,
    rank_race,
    run_shard,
    seed_generation_zero,
    select_elite,
    split_lockbox,
    summarize_fitness,
    top_quantile_band,
    variant_id,
    win_or_close_share,
    write_records,
)
from oracle_core.testing import FixedClock

SPACE = SearchSpace(
    (
        Dimension("alpha", DimKind.FLOAT, low=0.0, high=1.0),
        Dimension("depth", DimKind.INT, low=1, high=8),
        Dimension("scale", DimKind.LOG_FLOAT, low=0.01, high=10.0),
        Dimension("use_boost", DimKind.BOOL),
        Dimension("mode", DimKind.CATEGORICAL, choices=("a", "b", "c")),
    )
)


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #


def test_variant_id_is_stable_and_order_independent() -> None:
    a = Variant({"x": 1, "y": 2, "z": [3, 4]})
    b = Variant({"z": [3, 4], "y": 2, "x": 1})

    assert a.id == b.id == variant_id(a)
    assert variant_id({"x": 1, "y": 2, "z": [3, 4]}) == a.id
    assert len(a.id) == 64


def test_variant_id_changes_with_value() -> None:
    assert Variant({"x": 1}).id != Variant({"x": 2}).id
    assert Variant({"x": 1}).id != Variant({"x": 1.0000001}).id


# --------------------------------------------------------------------------- #
# Search space validation
# --------------------------------------------------------------------------- #


def test_dimension_validation() -> None:
    with pytest.raises(ValueError):
        Dimension("bad", DimKind.FLOAT)  # missing bounds
    with pytest.raises(ValueError):
        Dimension("bad", DimKind.LOG_FLOAT, low=0.0, high=1.0)  # non-positive low
    with pytest.raises(ValueError):
        Dimension("bad", DimKind.CATEGORICAL)  # missing choices
    with pytest.raises(ValueError):
        Dimension("bad", DimKind.FLOAT, low=1.0, high=0.0)  # inverted


def test_search_space_rejects_duplicate_names() -> None:
    with pytest.raises(ValueError):
        SearchSpace(
            (
                Dimension("dup", DimKind.BOOL),
                Dimension("dup", DimKind.BOOL),
            )
        )


def test_sampled_variant_respects_bounds() -> None:
    rng = random.Random(7)
    variant = RandomSampler().sample(SPACE, rng)
    assert 0.0 <= variant.params["alpha"] <= 1.0
    assert 1 <= variant.params["depth"] <= 8
    assert 0.01 <= variant.params["scale"] <= 10.0
    assert isinstance(variant.params["use_boost"], bool)
    assert variant.params["mode"] in ("a", "b", "c")


# --------------------------------------------------------------------------- #
# Sharding
# --------------------------------------------------------------------------- #


def test_partition_variants_is_balanced_and_deterministic() -> None:
    variants = [Variant({"i": i}) for i in range(10)]
    shards = partition_variants(variants, 3)

    assert [len(s) for s in shards] == [4, 3, 3]
    # Every variant appears exactly once, round-robin order preserved.
    flat = [v.params["i"] for shard in shards for v in shard]
    assert sorted(flat) == list(range(10))
    assert shards[0][0].params["i"] == 0
    assert shards[1][0].params["i"] == 1


def test_partition_drops_empty_tail_shards() -> None:
    shards = partition_variants([Variant({"i": 0}), Variant({"i": 1})], 5)
    assert len(shards) == 2


def test_partition_rejects_bad_shard_count() -> None:
    with pytest.raises(ValueError):
        partition_variants([Variant({"i": 0})], 0)


# --------------------------------------------------------------------------- #
# Fitness
# --------------------------------------------------------------------------- #


def _result(vid: str, flags: list[tuple[bool, bool]]) -> SlateResult:
    obs = tuple(
        RankObservation(slate_id=f"s{i}", won=won, close=close, score=float(i))
        for i, (won, close) in enumerate(flags)
    )
    return SlateResult(variant_id=vid, observations=obs)


def test_win_or_close_share() -> None:
    result = _result("v", [(True, False), (False, True), (False, False), (False, False)])
    assert win_or_close_share(result) == 0.5


def test_win_or_close_share_empty_is_zero() -> None:
    assert win_or_close_share(SlateResult(variant_id="v", observations=())) == 0.0


def test_top_quantile_band() -> None:
    values = [0.1, 0.5, 0.9, 0.7, 0.3]
    # keep top 40% -> ceil(0.4*5)=2 -> band is 2nd best = 0.7
    assert top_quantile_band(values, quantile=0.4) == 0.7
    # keep everything
    assert top_quantile_band(values, quantile=1.0) == 0.1


def test_top_quantile_band_validates() -> None:
    with pytest.raises(ValueError):
        top_quantile_band([], quantile=0.5)
    with pytest.raises(ValueError):
        top_quantile_band([0.1], quantile=0.0)


def _record(vid: str, share: float, score: float = 0.0) -> VariantRecord:
    return VariantRecord(
        variant_id=vid,
        params={"id": vid},
        generation=0,
        fidelity_level=0,
        win_or_close_share=share,
        mean_score=score,
        slates=1,
    )


def test_select_elite_keeps_band_and_orders_best_first() -> None:
    records = [
        _record("a", 0.9),
        _record("b", 0.7),
        _record("c", 0.5),
        _record("d", 0.3),
    ]
    elite = select_elite(records, quantile=0.5)
    assert [r.variant_id for r in elite] == ["a", "b"]


def test_select_elite_retains_ties_at_band() -> None:
    records = [_record("a", 0.9), _record("b", 0.5), _record("c", 0.5), _record("d", 0.5)]
    # ceil(0.25*4)=1 -> band is 1st best = 0.9, only "a" qualifies
    elite = select_elite(records, quantile=0.25)
    assert [r.variant_id for r in elite] == ["a"]
    # a band that lands on a tie keeps all tied members
    elite2 = select_elite(records, quantile=0.5)
    assert {r.variant_id for r in elite2} == {"a", "b", "c", "d"}


# --------------------------------------------------------------------------- #
# Genetics
# --------------------------------------------------------------------------- #


def test_seed_generation_zero_count() -> None:
    rng = random.Random(1)
    variants = seed_generation_zero(SPACE, RandomSampler(), count=6, rng=rng)
    assert len(variants) == 6


def test_mutate_only_changes_some_dims_and_stays_in_bounds() -> None:
    rng = random.Random(123)
    base = RandomSampler().sample(SPACE, random.Random(0))
    mutated = mutate(base, SPACE, rng, rate=1.0)  # resample everything
    assert set(mutated.params) == set(base.params)
    assert 0.0 <= mutated.params["alpha"] <= 1.0
    assert mutated.params["mode"] in ("a", "b", "c")

    unchanged = mutate(base, SPACE, random.Random(0), rate=0.0)
    assert unchanged.params == base.params


def test_crossover_inherits_from_parents() -> None:
    a = Variant({"alpha": 0.1, "depth": 1, "scale": 0.5, "use_boost": True, "mode": "a"})
    b = Variant({"alpha": 0.9, "depth": 8, "scale": 5.0, "use_boost": False, "mode": "c"})
    child = crossover(a, b, SPACE, random.Random(3))
    for name in SPACE.names:
        assert child.params[name] in (a.params[name], b.params[name])


def test_breed_generation_carries_elites_and_fills_size() -> None:
    elites = [
        Variant({"alpha": 0.1, "depth": 1, "scale": 0.5, "use_boost": True, "mode": "a"}),
        Variant({"alpha": 0.9, "depth": 8, "scale": 5.0, "use_boost": False, "mode": "c"}),
    ]
    gen = breed_generation(
        elites, SPACE, RandomSampler(), random.Random(9), size=10, elite_carryover=2
    )
    assert len(gen) == 10
    assert gen[0].params == elites[0].params
    assert gen[1].params == elites[1].params


def test_breed_generation_cold_restart_without_elites() -> None:
    gen = breed_generation([], SPACE, RandomSampler(), random.Random(9), size=4)
    assert len(gen) == 4


# --------------------------------------------------------------------------- #
# Records + persistence
# --------------------------------------------------------------------------- #


def test_merge_shard_records_orders_deterministically() -> None:
    shard_a = [_record("a", 0.2), _record("c", 0.8)]
    shard_b = [_record("b", 0.5)]
    merged = merge_shard_records([shard_a, shard_b])
    assert [r.variant_id for r in merged] == ["c", "b", "a"]
    # order of shards does not matter
    assert merge_shard_records([shard_b, shard_a]) == merged


def test_write_records_roundtrip_and_hash(tmp_path: Path) -> None:
    records = [_record("a", 0.9, 1.5), _record("b", 0.4, 0.2)]
    info = write_records(tmp_path / "gen.json", records)

    on_disk = json.loads((tmp_path / "gen.json").read_text())
    assert [r["variant_id"] for r in on_disk] == ["a", "b"]
    assert info.size == (tmp_path / "gen.json").stat().st_size
    assert len(info.sha256) == 64


# --------------------------------------------------------------------------- #
# run_shard
# --------------------------------------------------------------------------- #


def test_run_shard_builds_records() -> None:
    def evaluate(variant: Variant, ctx: EvalContext) -> SlateResult:
        won = variant.params["depth"] > 4
        return SlateResult(
            variant_id=variant.id,
            observations=(RankObservation(slate_id="s0", won=won, close=False, score=1.0),),
        )

    variants = [Variant({"depth": 2}), Variant({"depth": 6})]
    ctx = EvalContext(
        fidelity=Fidelity(level=0), seed=1, generation=0, now=datetime(2026, 1, 1, tzinfo=UTC)
    )
    records = run_shard(variants, evaluate, ctx)
    by_id = {r.variant_id: r for r in records}
    assert by_id[Variant({"depth": 6}).id].win_or_close_share == 1.0
    assert by_id[Variant({"depth": 2}).id].win_or_close_share == 0.0


# --------------------------------------------------------------------------- #
# Stop policy
# --------------------------------------------------------------------------- #


def test_stop_policy_max_generations() -> None:
    policy = StopPolicy(max_generations=3)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert policy.decide(generation=0, best_share=0.1, now=now).stop is False
    decision = policy.decide(generation=2, best_share=0.1, now=now)
    assert decision.stop is True
    assert decision.reason == "max_generations_reached"


def test_stop_policy_target_and_deadline() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    target = StopPolicy(max_generations=100, target_share=0.8)
    assert target.decide(generation=0, best_share=0.85, now=now).reason == "target_share_reached"

    deadline = StopPolicy(max_generations=100, deadline=now)
    assert deadline.decide(generation=0, best_share=0.1, now=now).reason == "deadline_reached"


def test_stop_policy_validates() -> None:
    with pytest.raises(ValueError):
        StopPolicy(max_generations=0)
    with pytest.raises(ValueError):
        StopPolicy(max_generations=1, target_share=2.0)


# --------------------------------------------------------------------------- #
# Racer end-to-end determinism (FixedClock)
# --------------------------------------------------------------------------- #


def _make_racer(clock: FixedClock, records_dir: Path | None = None) -> Racer:
    # Deterministic objective: reward high alpha and deep trees. The optimum is
    # a fixed point in the space, so the elite share should climb over
    # generations. No sport, no I/O, no randomness in the evaluation itself.
    def evaluate(variant: Variant, ctx: EvalContext) -> SlateResult:
        alpha = float(variant.params["alpha"])
        depth = int(variant.params["depth"])
        quality = 0.6 * alpha + 0.4 * (depth / 8.0)
        obs = tuple(
            RankObservation(
                slate_id=f"s{i}",
                won=quality > 0.75,
                close=quality > 0.55,
                score=quality,
            )
            for i in range(ctx.fidelity.slate_budget or 4)
        )
        return SlateResult(variant_id=variant.id, observations=obs)

    return Racer(
        space=SPACE,
        evaluate=evaluate,
        clock=clock,
        sampler=RandomSampler(),
        population_size=16,
        elite_quantile=0.25,
        mutation_rate=0.2,
        elite_carryover=2,
        num_shards=3,
        fidelity_schedule=(Fidelity(level=0, slate_budget=4), Fidelity(level=1, slate_budget=8)),
        records_dir=records_dir,
    )


def test_racer_is_deterministic_with_fixed_clock() -> None:
    clock1 = FixedClock(datetime(2026, 9, 27, 16, 0, tzinfo=UTC))
    clock2 = FixedClock(datetime(2026, 9, 27, 16, 0, tzinfo=UTC))
    result1 = _make_racer(clock1).run(seed=2026, stop=StopPolicy(max_generations=4))
    result2 = _make_racer(clock2).run(seed=2026, stop=StopPolicy(max_generations=4))

    assert result1.generations == result2.generations == 4
    assert result1.stop_reason == "max_generations_reached"
    assert result1.best is not None and result2.best is not None
    assert result1.best.variant_id == result2.best.variant_id
    assert result1.best.win_or_close_share == result2.best.win_or_close_share
    # Full history matches record-for-record.
    ids1 = [[r.variant_id for r in gen] for gen in result1.history]
    ids2 = [[r.variant_id for r in gen] for gen in result2.history]
    assert ids1 == ids2


def test_racer_improves_and_persists(tmp_path: Path) -> None:
    clock = FixedClock(datetime(2026, 9, 27, 16, 0, tzinfo=UTC))
    result = _make_racer(clock, records_dir=tmp_path).run(
        seed=11, stop=StopPolicy(max_generations=5)
    )

    first_best = result.history[0][0].win_or_close_share
    last_best = result.history[-1][0].win_or_close_share
    assert last_best >= first_best  # elite band should not regress

    written = sorted(tmp_path.glob("generation-*.json"))
    assert len(written) == 5
    payload = json.loads(written[-1].read_text())
    assert payload[0]["variant_id"] == result.history[-1][0].variant_id


def test_racer_stops_on_deadline() -> None:
    clock = FixedClock(datetime(2026, 9, 27, 16, 20, tzinfo=UTC))
    deadline = clock() - timedelta(seconds=1)  # already past
    result = _make_racer(clock).run(seed=5, stop=StopPolicy(max_generations=100, deadline=deadline))
    assert result.stop_reason == "deadline_reached"
    assert result.generations == 1


# --------------------------------------------------------------------------- #
# FitConfig score classification (Refs #353 / #356)
# --------------------------------------------------------------------------- #


def test_fit_config_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="close_score_gap"):
        FitConfig(close_score_gap=-0.1)
    with pytest.raises(ValueError, match="close_score_pct"):
        FitConfig(close_score_pct=1.1)
    with pytest.raises(ValueError, match="min_races"):
        FitConfig(min_races=0)


def test_rank_race_marks_wins_ties_and_close_band() -> None:
    results = rank_race(
        {
            "alpha": 10.0,
            "bravo": 10.0,
            "charlie": 9.6,
            "delta": 8.9,
        },
        config=FitConfig(close_score_gap=0.5),
    )

    assert [result.result for result in results] == [
        FitResult.WIN,
        FitResult.WIN,
        FitResult.CLOSE,
        FitResult.OUT,
    ]


def test_rank_race_supports_lower_is_better_relative_close_band() -> None:
    results = rank_race(
        {
            "alpha": 100.0,
            "bravo": 104.0,
            "charlie": 109.0,
        },
        config=FitConfig(close_score_pct=0.05, higher_is_better=False),
    )

    assert [result.result for result in results] == [
        FitResult.WIN,
        FitResult.CLOSE,
        FitResult.OUT,
    ]


def test_summarize_fitness_uses_win_or_close_share_and_min_races() -> None:
    summaries = summarize_fitness(
        [
            {"alpha": 10.0, "bravo": 9.0, "charlie": 9.7},
            {"alpha": 8.0, "bravo": 8.0, "charlie": 7.6},
            {"bravo": 11.0, "charlie": 10.7},
        ],
        config=FitConfig(close_score_gap=0.5, min_races=3),
    )

    alpha = summaries["alpha"]
    assert alpha.races == 2
    assert alpha.wins == 2
    assert alpha.closes == 0
    assert alpha.win_or_close_share == 1.0
    assert alpha.eligible is False
    assert alpha.fitness == 0.0

    bravo = summaries["bravo"]
    assert bravo.races == 3
    assert bravo.wins == 2
    assert bravo.closes == 0
    assert bravo.losses == 1
    assert bravo.win_or_close_share == pytest.approx(2 / 3)
    assert bravo.eligible is True
    assert bravo.fitness == pytest.approx(2 / 3)

    charlie = summaries["charlie"]
    assert charlie.races == 3
    assert charlie.wins == 0
    assert charlie.closes == 3
    assert charlie.losses == 0
    assert charlie.win_or_close_share == 1.0
    assert charlie.fitness == 1.0


# --------------------------------------------------------------------------- #
# Lockbox + process pool
# --------------------------------------------------------------------------- #


def test_split_lockbox_holds_out_last_fraction() -> None:
    search, lockbox = split_lockbox([f"u{i}" for i in range(10)], fraction=0.20)
    assert search == tuple(f"u{i}" for i in range(8))
    assert lockbox == ("u8", "u9")


def test_split_lockbox_empty_and_single() -> None:
    assert split_lockbox([]) == ((), ())
    assert split_lockbox(["only"]) == (("only",), ())


def test_split_lockbox_rejects_bad_fraction() -> None:
    with pytest.raises(ValueError, match="fraction"):
        split_lockbox(["a", "b"], fraction=0.0)
    with pytest.raises(ValueError, match="fraction"):
        split_lockbox(["a", "b"], fraction=1.0)


def _double(value: int) -> int:
    """Module-level worker so process_pool_map can pickle it."""

    return value * 2


def test_process_pool_map_runs_picklable_worker() -> None:
    assert process_pool_map(_double, [1, 2, 3], max_workers=2) == [2, 4, 6]
    assert process_pool_map(_double, [], max_workers=1) == []
