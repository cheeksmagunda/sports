"""Unit and integration tests for dossier entry and gap computation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from oracle_core import (
    CensoringReason,
    Dossier,
    DossierEntry,
    EntryKind,
    Exactness,
    Gap,
)

from wnba_oracle.dossier import (
    _extract_player_ids,
    _gap_exactness,
    _realized_oracle,
    build_dossier,
)


class TestRealizedOracle:
    """Test theoretical ceiling computation."""

    def test_realizes_top_uncapped_lineup(self) -> None:
        pool = [
            {"real_score": 50.0, "card_boost": 0.5, "team_key": "A"},
            {"real_score": 45.0, "card_boost": 0.3, "team_key": "B"},
            {"real_score": 40.0, "card_boost": 0.2, "team_key": "C"},
            {"real_score": 35.0, "card_boost": 0.1, "team_key": "D"},
            {"real_score": 30.0, "card_boost": 0.0, "team_key": "E"},
        ]
        score = _realized_oracle(pool, cap=5)
        assert score > 0
        # Should be 50*(2.0+0.5) + 45*(1.8+0.3) + 40*(1.6+0.2) + 35*(1.4+0.1) + 30*(1.2+0)
        # = 125 + 94.5 + 72 + 52.5 + 36 = 380
        assert score == pytest.approx(380.0, abs=0.1)

    def test_respects_team_cap(self) -> None:
        pool = [
            {"real_score": 50.0, "card_boost": 0.0, "team_key": "A"},
            {"real_score": 49.0, "card_boost": 0.0, "team_key": "A"},
            {"real_score": 48.0, "card_boost": 0.0, "team_key": "A"},
            {"real_score": 47.0, "card_boost": 0.0, "team_key": "B"},
            {"real_score": 46.0, "card_boost": 0.0, "team_key": "C"},
            {"real_score": 45.0, "card_boost": 0.0, "team_key": "D"},
            {"real_score": 44.0, "card_boost": 0.0, "team_key": "E"},
        ]
        # Cap 2: can't take all three A players, must drop the 48
        score_cap2 = _realized_oracle(pool, cap=2)
        # Should pick: 50(A), 49(A), 47(B), 46(C), 45(D)
        # = 50*2.0 + 49*1.8 + 47*1.6 + 46*1.4 + 45*1.2
        # = 100 + 88.2 + 75.2 + 64.4 + 54 = 381.8
        assert score_cap2 == pytest.approx(381.8, abs=0.1)

    def test_returns_minus_one_on_empty_pool(self) -> None:
        assert _realized_oracle([], cap=2) == -1.0

    def test_returns_minus_one_on_insufficient_pool(self) -> None:
        pool = [
            {"real_score": 50.0, "card_boost": 0.0, "team_key": "A"},
            {"real_score": 40.0, "card_boost": 0.0, "team_key": "B"},
            {"real_score": 30.0, "card_boost": 0.0, "team_key": "C"},
        ]
        assert _realized_oracle(pool, cap=1) == -1.0

    def test_prunes_to_top_26_before_enumeration(self) -> None:
        pool = [
            {"real_score": float(100 - i), "card_boost": 0.0, "team_key": f"T{i % 10}"}
            for i in range(50)
        ]
        score = _realized_oracle(pool, cap=5)
        assert score > 0


class TestGapExactness:
    """Test gap exactness derivation from endpoint censoring."""

    def test_exact_when_both_uncensored(self) -> None:
        assert _gap_exactness(None, None) == Exactness.EXACT

    def test_lower_bound_when_one_endpoint_censored(self) -> None:
        assert _gap_exactness(CensoringReason.INCOMPLETE_LABELS, None) == Exactness.LOWER_BOUND
        assert _gap_exactness(None, CensoringReason.LEADERBOARD_DEPTH) == Exactness.LOWER_BOUND

    def test_lower_bound_when_both_censored(self) -> None:
        assert (
            _gap_exactness(
                CensoringReason.INCOMPLETE_LABELS,
                CensoringReason.LEADERBOARD_DEPTH,
            )
            == Exactness.LOWER_BOUND
        )

    def test_unknown_when_unknown_placement_involved(self) -> None:
        assert _gap_exactness(CensoringReason.UNKNOWN_PLACEMENT, None) == Exactness.UNKNOWN
        assert _gap_exactness(None, CensoringReason.UNKNOWN_PLACEMENT) == Exactness.UNKNOWN

    def test_lower_bound_when_ceiling_pruning_involved_even_if_uncensored(self) -> None:
        """_realized_oracle's top-26 prefix is not proven optimal under the
        team cap, so a gap touching the ceiling can never be EXACT even when
        both endpoints are otherwise uncensored."""
        assert _gap_exactness(None, None, involves_pruned_ceiling=True) == Exactness.LOWER_BOUND

    def test_unknown_still_wins_over_pruning_when_both_apply(self) -> None:
        assert (
            _gap_exactness(
                CensoringReason.UNKNOWN_PLACEMENT,
                None,
                involves_pruned_ceiling=True,
            )
            == Exactness.UNKNOWN
        )


class TestDossierEntry:
    """Test DossierEntry serialization."""

    def test_serializes_to_dict(self) -> None:
        entry = DossierEntry(
            kind=EntryKind.COMMITTED,
            score=100.5,
            achievable=True,
            slot_order_basis="committed",
            censor_reason=None,
        )
        d = entry.to_dict()
        assert d["kind"] == "committed"
        assert d["score"] == 100.5
        assert d["achievable"] is True
        assert d["slot_order_basis"] == "committed"
        assert d["censor_reason"] is None

    def test_serializes_with_censor_reason(self) -> None:
        entry = DossierEntry(
            kind=EntryKind.THEORETICAL_CEILING,
            score=150.0,
            achievable=False,
            slot_order_basis="optimal_resort",
            censor_reason=CensoringReason.INCOMPLETE_LABELS,
        )
        d = entry.to_dict()
        assert d["censor_reason"] == "incomplete_labels"


class TestGap:
    """Test Gap serialization."""

    def test_serializes_exact_gap(self) -> None:
        gap = Gap(
            from_kind=EntryKind.COMMITTED,
            to_kind=EntryKind.FIELD_BEST,
            value=10.5,
            exactness=Exactness.EXACT,
            from_censor=None,
            to_censor=None,
        )
        d = gap.to_dict()
        assert d["from_kind"] == "committed"
        assert d["to_kind"] == "field_best"
        assert d["value"] == 10.5
        assert d["exactness"] == "exact"


class TestDossier:
    """Test Dossier serialization."""

    def test_serializes_complete_dossier(self) -> None:
        entries = {
            EntryKind.COMMITTED: DossierEntry(
                kind=EntryKind.COMMITTED,
                score=100.0,
                achievable=True,
                slot_order_basis="committed",
                censor_reason=None,
            ),
            EntryKind.FIELD_BEST: DossierEntry(
                kind=EntryKind.FIELD_BEST,
                score=110.0,
                achievable=True,
                slot_order_basis="as_entered",
                censor_reason=None,
            ),
            EntryKind.THEORETICAL_CEILING: DossierEntry(
                kind=EntryKind.THEORETICAL_CEILING,
                score=150.0,
                achievable=False,
                slot_order_basis="optimal_resort",
                censor_reason=None,
            ),
        }
        dossier = Dossier(
            slate_date="2026-08-30",
            entries=entries,
            gap_to_field=Gap(
                from_kind=EntryKind.COMMITTED,
                to_kind=EntryKind.FIELD_BEST,
                value=10.0,
                exactness=Exactness.EXACT,
            ),
            gap_field_to_ceiling=Gap(
                from_kind=EntryKind.FIELD_BEST,
                to_kind=EntryKind.THEORETICAL_CEILING,
                value=40.0,
                exactness=Exactness.EXACT,
            ),
            gap_to_ceiling=Gap(
                from_kind=EntryKind.COMMITTED,
                to_kind=EntryKind.THEORETICAL_CEILING,
                value=50.0,
                exactness=Exactness.EXACT,
            ),
        )
        d = dossier.to_dict()
        assert d["slate_date"] == "2026-08-30"
        assert "committed" in d["entries"]
        assert d["entries"]["committed"]["score"] == 100.0
        assert d["gap_to_field"]["value"] == 10.0


class TestBuildDossierUnit:
    """Unit tests for build_dossier with mocked database."""

    @patch("wnba_oracle.dossier.get_api_engine")
    @patch("wnba_oracle.dossier.read_slate_labels")
    def test_returns_none_when_no_labels(self, mock_read_labels, mock_engine) -> None:
        mock_read_labels.return_value.is_empty.return_value = True
        result = build_dossier("2026-08-30")
        assert result is None

    @patch("wnba_oracle.dossier.get_api_engine")
    @patch("wnba_oracle.dossier.read_slate_labels")
    def test_builds_dossier_with_complete_data(self, mock_read_labels, mock_engine) -> None:
        mock_conn = MagicMock()
        mock_engine.return_value.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=None)

        lineup_row = MagicMock()
        # Real frozen_lineups.lineup JSONB shape: a dict, not a bare list.
        lineup_row.lineup = {
            "player_ids": [100, 101, 102, 103, 104],
            "slot_multipliers": [2.0, 1.8, 1.6, 1.4, 1.2],
            "lineup_score_p50": 150.0,
            "per_player": [],
        }

        leaderboard_row = MagicMock()
        leaderboard_row.rank = 1
        leaderboard_row.score = 120.0
        leaderboard_row.lineup = json.dumps([200, 201, 202, 203, 204])
        leaderboard_row.num_brawlers = 6800

        mock_conn.execute.side_effect = [
            MagicMock(first=MagicMock(return_value=lineup_row)),
            MagicMock(first=MagicMock(return_value=leaderboard_row)),
            MagicMock(first=MagicMock(return_value=None)),
        ]

        label_rows = [
            {
                "platform_player_id": 100,
                "slate_date": "2026-08-30",
                "real_score": 40.0,
                "card_boost": 0.5,
                "team_key": "A",
            },
            {
                "platform_player_id": 101,
                "slate_date": "2026-08-30",
                "real_score": 35.0,
                "card_boost": 0.3,
                "team_key": "B",
            },
            {
                "platform_player_id": 102,
                "slate_date": "2026-08-30",
                "real_score": 30.0,
                "card_boost": 0.2,
                "team_key": "C",
            },
            {
                "platform_player_id": 103,
                "slate_date": "2026-08-30",
                "real_score": 25.0,
                "card_boost": 0.1,
                "team_key": "D",
            },
            {
                "platform_player_id": 104,
                "slate_date": "2026-08-30",
                "real_score": 20.0,
                "card_boost": 0.0,
                "team_key": "E",
            },
            {
                "platform_player_id": 200,
                "slate_date": "2026-08-30",
                "real_score": 50.0,
                "card_boost": 0.5,
                "team_key": "F",
            },
            {
                "platform_player_id": 201,
                "slate_date": "2026-08-30",
                "real_score": 45.0,
                "card_boost": 0.3,
                "team_key": "G",
            },
            {
                "platform_player_id": 202,
                "slate_date": "2026-08-30",
                "real_score": 40.0,
                "card_boost": 0.2,
                "team_key": "H",
            },
            {
                "platform_player_id": 203,
                "slate_date": "2026-08-30",
                "real_score": 35.0,
                "card_boost": 0.1,
                "team_key": "I",
            },
            {
                "platform_player_id": 204,
                "slate_date": "2026-08-30",
                "real_score": 30.0,
                "card_boost": 0.0,
                "team_key": "J",
            },
        ]
        # Pad to a full slate (>=37 rows) so the ceiling is uncensored. The
        # coverage threshold counts THIS slate's rows now that the pool is
        # slate-scoped, so we need enough same-slate labels, not a mocked len().
        label_rows += [
            {
                "platform_player_id": 300 + i,
                "slate_date": "2026-08-30",
                "real_score": 10.0 + i,
                "card_boost": 0.0,
                "team_key": f"T{i % 6}",
            }
            for i in range(27)
        ]

        mock_df = MagicMock()
        mock_df.is_empty.return_value = False
        mock_df.to_dicts.return_value = label_rows
        mock_df.__len__ = MagicMock(return_value=len(label_rows))
        mock_read_labels.return_value = mock_df

        result = build_dossier("2026-08-30", engine=mock_engine.return_value)

        assert result is not None
        assert result.slate_date == "2026-08-30"
        assert EntryKind.COMMITTED in result.entries
        assert EntryKind.FIELD_BEST in result.entries
        assert EntryKind.THEORETICAL_CEILING in result.entries

        # Verify entry kinds
        assert result.entries[EntryKind.COMMITTED].kind == EntryKind.COMMITTED
        assert result.entries[EntryKind.FIELD_BEST].kind == EntryKind.FIELD_BEST
        assert result.entries[EntryKind.THEORETICAL_CEILING].kind == (EntryKind.THEORETICAL_CEILING)

        # Verify achievability
        assert result.entries[EntryKind.COMMITTED].achievable is True
        assert result.entries[EntryKind.FIELD_BEST].achievable is True
        assert result.entries[EntryKind.THEORETICAL_CEILING].achievable is False

        # Verify slot order basis
        assert result.entries[EntryKind.COMMITTED].slot_order_basis == "committed"
        assert result.entries[EntryKind.FIELD_BEST].slot_order_basis == "as_entered"
        assert result.entries[EntryKind.THEORETICAL_CEILING].slot_order_basis == "optimal_resort"

        # Verify gaps exist and have correct structure
        assert result.gap_to_field.from_kind == EntryKind.COMMITTED
        assert result.gap_to_field.to_kind == EntryKind.FIELD_BEST
        assert result.gap_field_to_ceiling.from_kind == EntryKind.FIELD_BEST
        assert result.gap_field_to_ceiling.to_kind == EntryKind.THEORETICAL_CEILING
        assert result.gap_to_ceiling.from_kind == EntryKind.COMMITTED
        assert result.gap_to_ceiling.to_kind == EntryKind.THEORETICAL_CEILING

        # The ceiling entry itself is uncensored here (37 labels), but its
        # score comes from _realized_oracle's top-26-pruned brute force,
        # which is not proven optimal under the team cap -- so any gap
        # touching it must be labeled lower_bound, never exact.
        assert result.entries[EntryKind.THEORETICAL_CEILING].censor_reason is None
        assert result.gap_field_to_ceiling.exactness == Exactness.LOWER_BOUND
        assert result.gap_to_ceiling.exactness == Exactness.LOWER_BOUND


class TestExtractPlayerIds:
    """The live /dossier 500 regression: frozen_lineups.lineup is a JSONB
    object ({"player_ids": [...]}) that psycopg returns as a dict, not the
    bare list the reader used to assume."""

    def test_extracts_from_stored_dict_payload(self) -> None:
        payload = {
            "player_ids": [100, 101, 102, 103, 104],
            "slot_multipliers": [2.0, 1.8, 1.6, 1.4, 1.2],
            "per_player": [{"player_id": 100}],
        }
        assert _extract_player_ids(payload) == [100, 101, 102, 103, 104]

    def test_extracts_from_json_string_of_dict(self) -> None:
        payload = json.dumps({"player_ids": [1, 2, 3, 4, 5]})
        assert _extract_player_ids(payload) == [1, 2, 3, 4, 5]

    def test_accepts_legacy_bare_list(self) -> None:
        assert _extract_player_ids([9, 8, 7, 6, 5]) == [9, 8, 7, 6, 5]

    def test_accepts_json_string_of_list(self) -> None:
        assert _extract_player_ids(json.dumps([9, 8, 7])) == [9, 8, 7]

    def test_dict_without_player_ids_returns_none(self) -> None:
        assert _extract_player_ids({"slot_multipliers": [1.0]}) is None

    def test_invalid_json_returns_none(self) -> None:
        assert _extract_player_ids("{not json") is None

    def test_unexpected_type_returns_none(self) -> None:
        assert _extract_player_ids(12345) is None


def _mock_engine_with_rows(mock_engine, lineup_row, leaderboard_row) -> MagicMock:
    mock_conn = MagicMock()
    mock_engine.return_value.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=None)
    mock_conn.execute.side_effect = [
        MagicMock(first=MagicMock(return_value=lineup_row)),
        MagicMock(first=MagicMock(return_value=leaderboard_row)),
    ]
    return mock_conn


def _labels_df(rows: list[dict]) -> MagicMock:
    df = MagicMock()
    df.is_empty.return_value = False
    df.to_dicts.return_value = rows
    df.__len__ = MagicMock(return_value=len(rows))
    return df


class TestBuildDossierShapeAndScoping:
    """Regression coverage for the two live defects: the committed lineup is a
    dict payload, and the theoretical ceiling must be scoped to one slate."""

    @patch("wnba_oracle.dossier.get_api_engine")
    @patch("wnba_oracle.dossier.read_slate_labels")
    def test_build_dossier_reads_committed_from_dict_payload(
        self, mock_read_labels, mock_engine
    ) -> None:
        lineup_row = MagicMock()
        lineup_row.lineup = {
            "player_ids": [100, 101, 102, 103, 104],
            "slot_multipliers": [2.0, 1.8, 1.6, 1.4, 1.2],
            "per_player": [],
        }
        leaderboard_row = MagicMock()
        leaderboard_row.rank = 1
        leaderboard_row.score = 120.0

        _mock_engine_with_rows(mock_engine, lineup_row, leaderboard_row)

        rows = [
            {
                "platform_player_id": 100 + i,
                "slate_date": "2026-08-30",
                "real_score": 40.0 - i,
                "card_boost": 0.0,
                "team_key": f"T{i % 6}",
            }
            for i in range(40)
        ]
        mock_read_labels.return_value = _labels_df(rows)

        result = build_dossier("2026-08-30", engine=mock_engine.return_value)

        assert result is not None
        committed = result.entries[EntryKind.COMMITTED]
        # All five committed players have labels this slate -> achievable, exact.
        assert committed.achievable is True
        assert committed.censor_reason is None
        assert committed.score > 0

    @patch("wnba_oracle.dossier.get_api_engine")
    @patch("wnba_oracle.dossier.read_slate_labels")
    def test_ceiling_ignores_other_slates(self, mock_read_labels, mock_engine) -> None:
        """A monster score on a different slate must not leak into this slate's
        theoretical ceiling."""
        lineup_row = MagicMock()
        lineup_row.lineup = {"player_ids": [1, 2, 3, 4, 5]}
        leaderboard_row = MagicMock()
        leaderboard_row.rank = 1
        leaderboard_row.score = 50.0

        _mock_engine_with_rows(mock_engine, lineup_row, leaderboard_row)

        target = [
            {
                "platform_player_id": i,
                "slate_date": "2026-08-30",
                "real_score": 10.0,
                "card_boost": 0.0,
                "team_key": f"T{i % 6}",
            }
            for i in range(1, 41)
        ]
        # Same player ids on a different slate with enormous scores.
        other = [
            {
                "platform_player_id": i,
                "slate_date": "2026-08-29",
                "real_score": 9999.0,
                "card_boost": 0.0,
                "team_key": f"T{i % 6}",
            }
            for i in range(1, 41)
        ]
        mock_read_labels.return_value = _labels_df(target + other)

        result = build_dossier("2026-08-30", engine=mock_engine.return_value)

        assert result is not None
        ceiling = result.entries[EntryKind.THEORETICAL_CEILING]
        # Five players at 10.0 with default slot bases (2.0..1.2) sum to 80.0.
        # A cross-slate leak would drive this into the tens of thousands.
        assert ceiling.score < 100.0

    @patch("wnba_oracle.dossier.get_api_engine")
    @patch("wnba_oracle.dossier.read_slate_labels")
    def test_returns_none_when_slate_has_no_labels(self, mock_read_labels, mock_engine) -> None:
        lineup_row = MagicMock()
        lineup_row.lineup = {"player_ids": [1, 2, 3, 4, 5]}
        _mock_engine_with_rows(mock_engine, lineup_row, None)

        # Labels exist, but only for a different slate.
        other = [
            {
                "platform_player_id": i,
                "slate_date": "2026-08-29",
                "real_score": 10.0,
                "card_boost": 0.0,
                "team_key": "A",
            }
            for i in range(1, 6)
        ]
        mock_read_labels.return_value = _labels_df(other)

        assert build_dossier("2026-08-30", engine=mock_engine.return_value) is None

    @patch("wnba_oracle.dossier.get_api_engine")
    @patch("wnba_oracle.dossier.read_slate_labels")
    def test_ceiling_censored_when_slate_coverage_thin(self, mock_read_labels, mock_engine) -> None:
        lineup_row = MagicMock()
        lineup_row.lineup = {"player_ids": [1, 2, 3, 4, 5]}
        leaderboard_row = MagicMock()
        leaderboard_row.rank = 1
        leaderboard_row.score = 50.0
        _mock_engine_with_rows(mock_engine, lineup_row, leaderboard_row)

        # Only 6 slate rows (< 37 threshold) -> ceiling censored.
        rows = [
            {
                "platform_player_id": i,
                "slate_date": "2026-08-30",
                "real_score": 10.0,
                "card_boost": 0.0,
                "team_key": f"T{i}",
            }
            for i in range(1, 7)
        ]
        mock_read_labels.return_value = _labels_df(rows)

        result = build_dossier("2026-08-30", engine=mock_engine.return_value)
        assert result is not None
        ceiling = result.entries[EntryKind.THEORETICAL_CEILING]
        assert ceiling.censor_reason == CensoringReason.INCOMPLETE_LABELS
