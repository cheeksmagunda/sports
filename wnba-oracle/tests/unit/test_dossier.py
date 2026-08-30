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
        assert (
            _gap_exactness(CensoringReason.INCOMPLETE_LABELS, None)
            == Exactness.LOWER_BOUND
        )
        assert (
            _gap_exactness(None, CensoringReason.LEADERBOARD_DEPTH)
            == Exactness.LOWER_BOUND
        )

    def test_lower_bound_when_both_censored(self) -> None:
        assert (
            _gap_exactness(
                CensoringReason.INCOMPLETE_LABELS,
                CensoringReason.LEADERBOARD_DEPTH,
            )
            == Exactness.LOWER_BOUND
        )

    def test_unknown_when_unknown_placement_involved(self) -> None:
        assert (
            _gap_exactness(CensoringReason.UNKNOWN_PLACEMENT, None)
            == Exactness.UNKNOWN
        )
        assert (
            _gap_exactness(None, CensoringReason.UNKNOWN_PLACEMENT)
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
        mock_engine.return_value.connect.return_value.__enter__ = MagicMock(
            return_value=mock_conn
        )
        mock_engine.return_value.connect.return_value.__exit__ = MagicMock(
            return_value=None
        )

        lineup_row = MagicMock()
        lineup_row.lineup_json = json.dumps([100, 101, 102, 103, 104])
        lineup_row.lineup = [100, 101, 102, 103, 104]

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

        mock_df = MagicMock()
        mock_df.is_empty.return_value = False
        mock_df.to_dicts.return_value = label_rows
        mock_df.__len__ = MagicMock(return_value=10)
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
        assert result.entries[EntryKind.THEORETICAL_CEILING].kind == (
            EntryKind.THEORETICAL_CEILING
        )

        # Verify achievability
        assert result.entries[EntryKind.COMMITTED].achievable is True
        assert result.entries[EntryKind.FIELD_BEST].achievable is True
        assert result.entries[EntryKind.THEORETICAL_CEILING].achievable is False

        # Verify slot order basis
        assert result.entries[EntryKind.COMMITTED].slot_order_basis == "committed"
        assert result.entries[EntryKind.FIELD_BEST].slot_order_basis == "as_entered"
        assert (
            result.entries[EntryKind.THEORETICAL_CEILING].slot_order_basis
            == "optimal_resort"
        )

        # Verify gaps exist and have correct structure
        assert result.gap_to_field.from_kind == EntryKind.COMMITTED
        assert result.gap_to_field.to_kind == EntryKind.FIELD_BEST
        assert result.gap_field_to_ceiling.from_kind == EntryKind.FIELD_BEST
        assert result.gap_field_to_ceiling.to_kind == EntryKind.THEORETICAL_CEILING
        assert result.gap_to_ceiling.from_kind == EntryKind.COMMITTED
        assert result.gap_to_ceiling.to_kind == EntryKind.THEORETICAL_CEILING
