from fastapi.testclient import TestClient

from main import app


def test_health_without_cloud_configuration():
    assert TestClient(app).get("/health").json()["status"] == "ok"
