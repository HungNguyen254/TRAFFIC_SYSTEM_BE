from fastapi import Request
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.config import settings
from app.core.database import get_session
from app.core.limiter import limiter
from app.main import app


def test_limiter_is_attached_to_app():
    assert hasattr(app.state, "limiter")
    assert app.state.limiter is not None
    assert settings.RATE_LIMIT_DEFAULT == "60/minute"
    assert settings.RATE_LIMIT_ENABLED is True


@app.get("/api/test-rate-limit-unit")
@limiter.limit("1/minute")
def _dummy_rate_limited_endpoint(request: Request):
    return {"status": "ok"}


def test_rate_limit_exceeded_response_format():
    client = TestClient(app)
    # First call succeeds
    res1 = client.get("/api/test-rate-limit-unit")
    assert res1.status_code == 200

    # Second call exceeds limit
    res2 = client.get("/api/test-rate-limit-unit")
    assert res2.status_code == 429
    data = res2.json()
    assert data["status_code"] == 429
    assert data["error"] == "RATE_LIMIT_EXCEEDED"
    assert data["message"] == "Quá nhiều yêu cầu. Vui lòng thử lại sau!"
    assert data["data"] is None
    assert "Retry-After" in res2.headers
    retry_after = int(res2.headers["Retry-After"])
    assert 1 <= retry_after <= 60


def test_rate_limit_disabled(monkeypatch):
    monkeypatch.setattr(limiter, "enabled", False)
    client = TestClient(app, client=("10.0.0.99", 12345))
    for _ in range(5):
        res = client.get("/api/test-rate-limit-unit")
        assert res.status_code == 200


def test_auth_login_rate_limit():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(app, client=("10.0.0.1", 12345)) as client:
            # First 5 calls return 401 (invalid credentials) but do not get 429
            for _ in range(5):
                res = client.post(
                    "/api/v1/auth/login",
                    json={"email": "wrong@example.com", "password": "BadPassword"},
                )
                assert res.status_code == 401

            # 6th call must exceed limit and return 429
            res6 = client.post(
                "/api/v1/auth/login",
                json={"email": "wrong@example.com", "password": "BadPassword"},
            )
            assert res6.status_code == 429
            data = res6.json()
            assert data["error"] == "RATE_LIMIT_EXCEEDED"

            # A different IP address is not blocked
            with TestClient(app, client=("10.0.0.2", 12345)) as client2:
                res_other_ip = client2.post(
                    "/api/v1/auth/login",
                    json={"email": "wrong@example.com", "password": "BadPassword"},
                )
                assert res_other_ip.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_chatbot_rate_limit():
    with TestClient(app, client=("10.0.0.3", 12345)) as client:
        # 10 calls to /api/v1/chatbot/chat succeed
        for _ in range(10):
            res = client.post("/api/v1/chatbot/chat", json={"message": "Xin chào tình hình kẹt xe"})
            assert res.status_code == 200

        # 11th call must return 429
        res11 = client.post("/api/v1/chatbot/chat", json={"message": "Xin chào tình hình kẹt xe"})
        assert res11.status_code == 429
        assert res11.json()["error"] == "RATE_LIMIT_EXCEEDED"
