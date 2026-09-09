"""Corpus C: scoring-law verification, boost recovery, and censoring honesty."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from nfl_oracle.contests.boosts import (
    boost_from_multiplier,
    boost_histogram,
    boost_leverage_table,
    fit_boost_rank_curve,
    observe_boosts,
    snap_boost,
)
from nfl_oracle.contests.collector import contest_url
from nfl_oracle.contests.field import counterfactual_best, profile_entry, study_contest
from nfl_oracle.contests.parse import (
    ContestParseError,
    load_contest,
    parse_contest_record,
    parse_draft_stats,
    parse_entries,
    verify_scoring_law,
)
from nfl_oracle.contests.schema import OBSERVED_SLOT_MULTIPLIERS
from nfl_oracle.contests.store import ContestStore, ScanCursor

SLOTS = OBSERVED_SLOT_MULTIPLIERS


def _card(player_id: int, order: int, value: float, boost: float) -> dict[str, object]:
    slot = SLOTS[order]
    return {
        "playerId": player_id,
        "id": player_id,
        "order": order,
        "multiplier": slot + boost,
        "multiplierBonus": boost,
        "value": str(value),
        "score": value * (slot + boost),
        "realRank": player_id,
        "isExact": False,
        "teamId": 30 if player_id % 2 else 21,
        "displayName": f"P. {player_id}",
        "injuryStatus": None,
    }


def _entry(entry_id: int, rank: int, cards: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": entry_id,
        "rank": rank,
        "score": str(round(sum(float(c["score"]) for c in cards), 2)),
        "payout": 0,
        "wager": 0,
        "type": "general",
        "additionalInfo": {"lineup": cards},
    }


def _meta(contest_id: int, *, finalized: bool = True, entrants: int = 20841) -> dict[str, object]:
    return {
        "info": {
            "isLocked": True,
            "contest": {
                "id": contest_id,
                "sport": "nfl",
                "day": "2025-09-15",
                "endDay": "2025-09-15",
                "season": 2025,
                "numBrawlers": entrants,
                "isFinalized": finalized,
                "commentCount": 3,
                "createdAt": "2025-09-14T11:00:20.202Z",
                "processedAt": "2025-09-16T05:29:37.364Z",
                "gameId": None,
                "additionalInfo": {"lineupSize": 5},
            },
        }
    }


DRAFTINFO = {
    "info": {
        "sport": "nfl",
        "day": "2025-09-15",
        "endDay": "2025-09-15",
        "lineupSize": 5,
        "defaultMultipliers": list(SLOTS),
        "raxContestPoolDetails": {
            "options": [
                {"key": "top10", "percent": 0.1, "payout": 7, "wagerOptions": [100]},
                {"key": "top20", "percent": 0.2, "payout": 3.5, "wagerOptions": [100]},
            ]
        },
    }
}

PAYOUTINFO = {"info": {"payoutInfoItems": [{"rankDisplay": "1st", "prizeAmount": 100}]}}


def test_boost_recovery_matches_provider_arithmetic() -> None:
    # Values taken from live contest 870: slot 1.6 + boost 2.3 = 3.9.
    assert boost_from_multiplier(3.9, 1.6) == 2.3
    assert boost_from_multiplier(4.2, 1.4) == 2.8
    assert boost_from_multiplier(2.0, 2.0) == 0.0
    assert snap_boost(1.4000000000000001) == 1.4


def test_boost_recovery_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        boost_from_multiplier(9.0, 1.2)


def test_entry_parsing_enforces_the_scoring_law() -> None:
    cards = [
        _card(101 + i, i, 4.0 - i * 0.5, boost) for i, boost in enumerate([0, 1.0, 2.3, 3.0, 0])
    ]
    entries = parse_entries({"entries": [_entry(1, 1, cards)]}, contest_id=870)
    assert len(entries) == 1
    entry = entries[0]
    assert [p.slot for p in entry.picks] == [1, 2, 3, 4, 5]
    assert entry.picks[2].card_boost == 2.3
    verified, error = verify_scoring_law(entries)
    assert verified and error is None


def test_entry_parsing_rejects_a_broken_score_law() -> None:
    cards = [_card(201 + i, i, 3.0, 0.0) for i in range(5)]
    cards[0]["score"] = 999.0  # provider arithmetic that does not decompose
    with pytest.raises(ValueError):
        parse_entries({"entries": [_entry(2, 1, cards)]}, contest_id=870)


def test_ordering_regret_is_zero_only_for_a_sorted_lineup() -> None:
    ascending = [_card(301 + i, i, 1.0 + i, 0.0) for i in range(5)]  # worst value in best slot
    bad = parse_entries({"entries": [_entry(3, 1, ascending)]}, contest_id=870)[0]
    profile = profile_entry(bad)
    assert profile.slot_regret is not None and profile.slot_regret > 0
    assert profile.ordering_optimal is False

    descending = [_card(311 + i, i, 5.0 - i, 0.0) for i in range(5)]
    good = parse_entries({"entries": [_entry(4, 1, descending)]}, contest_id=870)[0]
    assert profile_entry(good).ordering_optimal is True


def test_counterfactual_best_beats_every_saved_entry(tmp_path) -> None:
    store = ContestStore(tmp_path / "corpus_c")
    now = datetime.now(UTC)
    cards = [_card(401 + i, i, 4.0 - i * 0.4, 0.0) for i in range(5)]
    stats = {
        "draftStats": [
            {
                "sectionName": "highestBoostedValuePlayers",
                "players": [
                    {
                        "playerId": 401 + i,
                        "multiplierBonus": 0.0,
                        "value": str(4.0 - i * 0.4),
                        "count": 10 - i,
                        "avgMultiplier": 1.6,
                        "avgPosition": 3.0,
                        "mostCommonPosition": "3",
                        "player": {"id": 401 + i, "firstName": "P", "lastName": str(i)},
                    }
                    for i in range(6)
                ],
            }
        ]
    }
    for route, payload in [
        ("meta", _meta(900)),
        ("draftinfo", DRAFTINFO),
        ("payoutinfo", PAYOUTINFO),
        ("entries", {"entries": [_entry(5, 1, cards)]}),
        ("stats", stats),
    ]:
        store.write_route(900, route, payload, source_url="test", http_status=200, captured_at=now)
    parsed = load_contest(store, 900)
    assert parsed is not None and parsed.law_verified
    best = counterfactual_best(parsed)
    assert best is not None
    saved = parsed.entries[0].total_from_picks()
    assert saved is not None and best.score >= saved - 1e-9

    study = study_contest(parsed)
    assert study is not None
    # 20,841 entrants against one visible entry is censored, and says so.
    assert study.censored is True
    assert study.visible_entries == 1
    assert study.law_verified is True


def test_store_round_trip_detects_tampering(tmp_path) -> None:
    store = ContestStore(tmp_path / "corpus_c")
    store.write_route(
        11, "meta", _meta(11), source_url="u", http_status=200, captured_at=datetime.now(UTC)
    )
    assert store.read_route(11, "meta") is not None
    path = store.contest_dir(11) / "meta.json"
    path.write_text(json.dumps({"info": {"contest": {"id": 11}}}))
    with pytest.raises(ValueError):
        store.read_route(11, "meta")


def test_store_redacts_account_identity(tmp_path) -> None:
    store = ContestStore(tmp_path / "corpus_c")
    payload = dict(_meta(12))
    payload["userId"] = 4242
    payload["user"] = {"userId": 4242, "email": "a@b.c"}
    store.write_route(
        12, "meta", payload, source_url="u", http_status=200, captured_at=datetime.now(UTC)
    )
    raw = (store.contest_dir(12) / "meta.json").read_text()
    assert "userId" not in raw and "a@b.c" not in raw


def test_cursor_resumes_without_refetching(tmp_path) -> None:
    path = tmp_path / "cursor.json"
    cursor = ScanCursor()
    cursor.nfl_collected.append(870)
    cursor.other_sport["871"] = "mlb"
    cursor.absent["872"] = 403
    cursor.failed["873"] = "transport:ReadTimeout"
    cursor.save(path)
    reloaded = ScanCursor.load(path)
    assert reloaded.resolved() == {870, 871, 872}
    assert reloaded.pending([870, 871, 872, 873, 874]) == [873, 874]
    assert reloaded.pending([873, 874], retry_failed=False) == [874]


def test_zero_boost_table_is_detected_not_silently_optimized() -> None:
    week_one = [{"multiplierBonus": 0} for _ in range(50)]
    observation = observe_boosts(2141, week_one, captured_at="2026-09-08T23:54:24Z")
    assert observation.all_zero is True
    assert observation.published is False
    assert observation.max_boost == 0.0

    week_two = [{"multiplierBonus": b} for b in (0.0, 1.0, 2.3, 3.0)]
    published = observe_boosts(857, week_two, captured_at="2025-09-11T18:00:00Z")
    assert published.published is True
    assert published.all_zero is False
    assert published.distinct_boosts == (0.0, 1.0, 2.3, 3.0)


def test_leverage_table_quantifies_the_boost_advantage() -> None:
    table = boost_leverage_table([0.0, 1.0, 3.0])
    # A max-boost card in the worst slot needs only ~48% of a zero-boost card's
    # value, in the best slot, to tie it.
    assert table["max_effective_multiplier"] == pytest.approx(5.0)
    assert table["value_ratio_to_match"] == pytest.approx(2.0 / 4.2, rel=1e-6)
    assert boost_leverage_table([]) == {}
    assert boost_histogram([0.0, 0.0, 3.0]) == {"0.0": 2, "3.0": 1}


def test_boost_rank_curve_is_monotone_on_provider_shaped_data() -> None:
    observations = (
        [(5, 0.0, 1), (8, 0.0, 1), (20, 0.5, 1), (22, 0.6, 1)]
        + [(60, 1.5, 2), (70, 1.6, 2), (200, 2.8, 2), (400, 3.0, 3)]
        + [(None, 3.0, 3)]
    )
    curve = fit_boost_rank_curve(observations)
    assert curve.monotone is True
    assert curve.n_contests == 3
    assert curve.predict(6) == 0.0
    assert curve.predict(None) == 3.0
    assert curve.predict(10_000) == 3.0


def test_contest_parse_rejects_a_foreign_payload() -> None:
    with pytest.raises(ContestParseError):
        parse_contest_record({}, captured_at=datetime.now(UTC))
    with pytest.raises(ContestParseError):
        parse_entries({}, contest_id=1)
    with pytest.raises(ContestParseError):
        parse_draft_stats({}, contest_id=1)


def test_collector_only_addresses_the_contest_read_family() -> None:
    assert contest_url(870, "meta").endswith("/games/playerratingcontest/870")
    assert contest_url(870, "entries").endswith("/games/playerratingcontest/870/entries")
    # There is no writable route anywhere in this package.
    import nfl_oracle.contests.collector as collector

    source = (collector.__file__ or "").replace(".pyc", ".py")
    text = open(source, encoding="utf-8").read()
    assert "PUT" not in text and "/lineup" not in text
