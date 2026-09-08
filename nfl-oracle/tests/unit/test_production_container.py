from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_production_container_is_role_split_and_secret_free() -> None:
    dockerfile = (ROOT / "Dockerfile.production").read_text()
    assert "nfl-pipeline serve" in dockerfile
    assert "nfl-pipeline worker" in dockerfile
    assert "NFL_PIPELINE_ROLE=api" in dockerfile
    assert "PLAYWRIGHT_BROWSERS_PATH" in dockerfile
    assert "storage_state.json" not in dockerfile
    assert "COPY nfl-oracle/data" not in dockerfile
    assert "alembic upgrade" not in dockerfile


def test_railway_config_points_at_nfl_production_image() -> None:
    railway = (ROOT / "railway.toml").read_text()
    assert 'dockerfilePath = "nfl-oracle/Dockerfile.production"' in railway
    assert "nfl-pipeline migrate" in railway
    assert "nfl-pipeline worker" in railway
