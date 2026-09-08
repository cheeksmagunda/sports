"""Edge cases: schedule density, empty coverage, posture, algebra override."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from nfl_oracle.calendar.schedule import (
    catalog_vs_schedule_density,
    parse_schedules_csv,
    summarize_schedule_density,
)
from nfl_oracle.calendar.season import season_label_for_date, season_week_for_date
from nfl_oracle.data.catalog import SeasonGameCatalog
from nfl_oracle.data.coverage_matrix import CoverageMatrixDocument
from nfl_oracle.data.density import summarize_coverage_density
from nfl_oracle.providers.auth_status import AuthProbeResult
from nfl_oracle.providers.five_card import (
    FiveCardProviderStub,
    ProviderContractStatus,
    ProviderReadiness,
)
from nfl_oracle.strategy.algebra import OBSERVED_DEFAULT_SLOT_MULTIPLIERS, contest_shadow_score
from nfl_oracle.strategy.posture import current_posture, posture_from_readiness
from nfl_oracle.strategy.schema import FiveCardAction, Posture

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _auth(*, usable: bool) -> AuthProbeResult:
    return AuthProbeResult(
        usable=usable,
        storage_state_path=None,
        storage_state_exists=False,
        env_path_set=False,
        env_b64gz_set=usable,
        device_uuid_set=False,
        device_name_set=False,
        token_cache_exists=False,
        sibling_wnba_storage_exists=False,
        notes=(),
    )


def test_empty_schedule_density() -> None:
    dens = summarize_schedule_density([])
    assert dens.season_count == 0
    assert dens.game_count == 0
    assert dens.mean_games_per_season == 0.0
    assert dens.min_games_per_season is None
    assert dens.team_count == 0


def test_empty_coverage_density() -> None:
    dens = summarize_coverage_density(
        catalog=SeasonGameCatalog(seasons={}),
        matrix=CoverageMatrixDocument(generated_at=None, seasons={}, gaps=[]),
    )
    assert dens.catalog_season_count == 0
    assert dens.catalog_seed_game_count == 0
    assert dens.known_ratio == 0.0
    assert dens.matrix_game_id_count == 0


def test_catalog_vs_schedule_zero_schedule() -> None:
    cmp = catalog_vs_schedule_density(catalog_seed_count=10, schedule_game_count=0)
    assert cmp["seed_to_schedule_ratio"] == 0.0
    assert cmp["schedule_games_beyond_seeds"] == 0
    assert cmp["contest_entry"] is False


def test_season_labels_offseason_and_jan() -> None:
    assert season_label_for_date(date(2026, 1, 12)) == 2025
    assert season_label_for_date(date(2026, 5, 1)) == 2026
    assert season_week_for_date(date(2026, 5, 1)).week is None


def test_posture_stub_verified_and_shadow_and_contest_defensive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "nfl_oracle.providers.five_card.probe_realsports_auth", lambda: _auth(usable=False)
    )
    stub = ProviderReadiness(
        status=ProviderContractStatus.STUB,
        contest_entry=False,
        auth=_auth(usable=True),
        unknown_rules=(),
        issue_refs=("#91",),
    )
    assert posture_from_readiness(stub) == Posture.SHADOW_ONLY
    verified = ProviderReadiness(
        status=ProviderContractStatus.VERIFIED,
        contest_entry=False,
        auth=_auth(usable=True),
        unknown_rules=(),
        issue_refs=("#91",),
    )
    assert posture_from_readiness(verified) == Posture.CAPTURE_ONLY
    # Defensive: even if contest_entry flipped, posture stays BLOCKED.
    leaked = ProviderReadiness(
        status=ProviderContractStatus.VERIFIED,
        contest_entry=True,
        auth=_auth(usable=True),
        unknown_rules=(),
        issue_refs=("#91",),
    )
    assert posture_from_readiness(leaked) == Posture.BLOCKED
    assert current_posture() in {Posture.BLOCKED, Posture.SHADOW_ONLY}


def test_contest_algebra_negative_override_edge() -> None:
    action = FiveCardAction(
        player_ids=(1, 2, 3, 4, 5),
        slot_multipliers=OBSERVED_DEFAULT_SLOT_MULTIPLIERS,
    )
    values = {1: -1.0, 2: 2.0, 3: 2.0, 4: 2.0, 5: 2.0}
    refused = contest_shadow_score(action, values)
    assert refused.total == 0.0
    assert refused.non_negative_branch is False
    forced = contest_shadow_score(action, values, allow_unresolved_negative=True)
    assert forced.non_negative_branch is False
    assert forced.total == pytest.approx((-1.0) * 2.0 + 2 * 1.8 + 2 * 1.6 + 2 * 1.4 + 2 * 1.2)
    assert "override" in forced.notes


def test_provider_stub_default_posture_blocked_without_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "nfl_oracle.providers.five_card.probe_realsports_auth", lambda: _auth(usable=False)
    )
    stub = FiveCardProviderStub()
    ready = stub.readiness()
    assert ready.contest_entry is False
    # Box / CI typically auth_missing → BLOCKED.
    assert posture_from_readiness(ready) in {Posture.BLOCKED, Posture.SHADOW_ONLY}


def test_parse_empty_csv_header_only() -> None:
    games = parse_schedules_csv("season,week,game_id,gameday,home_team,away_team\n")
    assert games == []
