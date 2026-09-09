import os

import pytest
from fastapi.testclient import TestClient

from evidencedesk.cli import migrate
from evidencedesk.config import settings
from evidencedesk.db import connection
from evidencedesk.ingest import seed
from main import app


@pytest.fixture
def db(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required for real PostgreSQL integration")
    if not url.rsplit("/", 1)[-1].startswith("evidencedesk_test"):
        pytest.fail("Integration database name must start with evidencedesk_test")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("MIGRATION_DATABASE_URL", url)
    monkeypatch.setenv("SERVICE_KEY", "test-service-key-" + "x" * 32)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("AI_MODE", "simulated")
    settings.cache_clear()
    migrate()
    with connection(migration=True) as conn:
        conn.execute("TRUNCATE evidence.sessions,evidence.usage_counters CASCADE")
    seed()
    yield
    settings.cache_clear()


@pytest.fixture
def client(db):
    with TestClient(app) as client:
        client.headers["X-Service-Key"] = settings().service_key.get_secret_value()
        yield client


@pytest.fixture
def owner(client):
    result = client.post("/sessions")
    assert result.status_code == 200, result.text
    client.headers["X-Session-Token"] = result.json()["token"]
    return client.get("/tickets").json()["tickets"]
