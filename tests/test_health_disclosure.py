from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import app


def test_health_check_healthy(monkeypatch):
    monkeypatch.setattr("app.main.check_db_connection", lambda: None)
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["database"] == "connected"
    assert data["status"] == "ok"


def test_health_check_does_not_leak_exception_details(monkeypatch):
    def mock_failing_db():
        raise OperationalError(
            "connection to server at 'db.internal.supabase.co' (10.0.0.5), port 5432 failed: FATAL: password authentication failed for user 'postgres'",
            None,
            None,
        )

    monkeypatch.setattr("app.main.check_db_connection", mock_failing_db)

    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()["data"]

    # Must return sanitized "disconnected"
    assert data["database"] == "disconnected"

    # Must NOT disclose internal server addresses, credentials, or driver strings
    assert "db.internal.supabase.co" not in response.text
    assert "10.0.0.5" not in response.text
    assert "FATAL" not in response.text
    assert "password authentication failed" not in response.text
