from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_production_container_is_role_split_and_secret_free() -> None:
    dockerfile = (ROOT / "Dockerfile.production").read_text()
    assert "nfl-pipeline serve" in dockerfile
    assert "nfl-pipeline worker" in dockerfile
    assert "NFL_PIPELINE_ROLE=api" in dockerfile
    assert "PLAYWRIGHT_BROWSERS_PATH" in dockerfile
    assert "storage_state.json" not in dockerfile
    bootstrap_dir = "/opt/nfl-oracle/bootstrap/schedule"
    data_copies = [
        line for line in dockerfile.splitlines() if line.startswith("COPY nfl-oracle/data/")
    ]
    assert data_copies == [
        f"COPY nfl-oracle/data/schedule/schedules.csv {bootstrap_dir}/schedules.csv",
        f"COPY nfl-oracle/data/schedule/README.md {bootstrap_dir}/README.md",
    ]
    assert "alembic upgrade" not in dockerfile


def test_railway_config_points_at_nfl_production_image() -> None:
    railway = (ROOT / "railway.toml").read_text()
    assert 'dockerfilePath = "nfl-oracle/Dockerfile.production"' in railway
    assert "nfl-pipeline migrate" in railway
    assert "nfl-pipeline worker" in railway
