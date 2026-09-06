"""Data catalog, features schema, calendar helpers."""

from __future__ import annotations

from datetime import date

from nfl_oracle.calendar.season import season_week_for_date
from nfl_oracle.data.catalog import load_season_game_catalog
from nfl_oracle.data.coverage import infer_status_from_seeds
from nfl_oracle.data.paths import resolve_data_paths
from nfl_oracle.features.schema import feature_registry, features_document
from nfl_oracle.identity.map import IdentityMap, IdentityRecord


def test_load_season_game_catalog_seeds() -> None:
    cat = load_season_game_catalog()
    assert 2002 in cat.seasons
    assert len(cat.game_ids(2025)) >= 1
    assert infer_status_from_seeds(cat.game_ids(2025)) == "known"
    assert infer_status_from_seeds(()) == "unknown"


def test_data_paths_layout() -> None:
    paths = resolve_data_paths()
    assert paths.catalog.name == "catalog"
    assert paths.schedule.name == "schedule"
    assert paths.raw_corpus_g.name == "corpus_g"
    game = paths.corpus_g_game(2002, 126323)
    assert game.parts[-2:] == ("2002", "126323")


def test_feature_registry_marks_same_slate_live_forbidden() -> None:
    specs = {s.name: s for s in feature_registry()}
    assert specs["same_slate_final_value"].live_ok is False
    assert specs["position_prior_mean"].live_ok is True
    assert specs["home_away"].live_ok is True
    doc = features_document()
    assert doc["version"] == 1
    assert doc["feature_count"] >= 28
    assert doc["live_ok_count"] >= 24


def test_calendar_season_labels() -> None:
    assert season_week_for_date(date(2026, 9, 10)).season == 2026
    assert season_week_for_date(date(2027, 1, 15)).season == 2026
    assert season_week_for_date(date(2026, 9, 10)).week is None


def test_identity_map() -> None:
    m = IdentityMap()
    m.upsert(IdentityRecord(real_player_id=42, display_name="Test", position="QB"))
    assert m.get(42) is not None
    assert len(m) == 1
