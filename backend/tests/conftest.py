"""Isolated SQLite test fixtures for LOOMOS Build Step 1 pytest suite."""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, build_engine, get_db
from app.main import create_app


@pytest.fixture()
def db_session_factory(tmp_path: Path):
    db_file = tmp_path / "test_loomos.db"
    test_engine = build_engine(f"sqlite:///{db_file.as_posix()}")
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    try:
        yield TestingSession, db_file
    finally:
        test_engine.dispose()


@pytest.fixture()
def client(db_session_factory):
    TestingSession, _ = db_session_factory
    app = create_app()

    def _override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as tc:
        yield tc


@pytest.fixture()
def initialized_owner(client: TestClient):
    """Initialize shed with 12 Shuttle + 4 Rapier looms and return auth headers + setup response."""
    res = client.post(
        "/api/v1/setup/initialize",
        json={
            "owner_full_name": "Ramasamy K",
            "owner_username": "owner_ram",
            "owner_password": "StrongPass123",
            "unit_name": "Nallagoundampalayam Weaving Works",
            "location": "Coimbatore, TN",
            "default_language": "en",
            "loom_groups": [
                {"count": 12, "prefix": "S-", "start_number": 1, "loom_type": "SHUTTLE", "rated_rpm": 160},
                {"count": 4, "prefix": "R-", "start_number": 1, "loom_type": "RAPIER", "rated_rpm": 380},
            ],
            "shifts_per_day": 2,
            "default_entry_mode": "DIRECT",
            "seed_mode": "CLEAN",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    return headers, body
