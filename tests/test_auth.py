from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.database import get_session
from app.main import app


def test_auth_full_lifecycle():
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

    with TestClient(app) as client:
        # 1. Register regular user
        reg_payload = {
            "email": "user@example.com",
            "password": "Password123!",
            "full_name": "Nguyễn Văn Người Dùng",
        }
        res_reg = client.post("/api/v1/auth/register", json=reg_payload)
        assert res_reg.status_code == 200
        reg_data = res_reg.json()
        assert reg_data["data"]["email"] == "user@example.com"
        assert reg_data["data"]["role"] == "user"

        # 2. Duplicate registration fails
        res_dup = client.post("/api/v1/auth/register", json=reg_payload)
        assert res_dup.status_code == 400

        # 3. Login wrong password fails
        res_wrong_login = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "WrongPassword"},
        )
        assert res_wrong_login.status_code == 401

        # 4. Login success returns access token
        res_login = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "Password123!"},
        )
        assert res_login.status_code == 200
        token_data = res_login.json()["data"]
        assert "access_token" in token_data
        token = token_data["access_token"]

        # 5. Get /me with valid token
        headers = {"Authorization": f"Bearer {token}"}
        res_me = client.get("/api/v1/auth/me", headers=headers)
        assert res_me.status_code == 200
        assert res_me.json()["data"]["email"] == "user@example.com"

        # 6. Malformed token returns 401
        res_bad_token = client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.value"}
        )
        assert res_bad_token.status_code == 401

        # 7. Attempting privilege escalation via public registration is blocked (role remains 'user')
        admin_attempt_payload = {
            "email": "hacker@example.com",
            "password": "Password123!",
            "full_name": "Attacker",
            "role": "admin",
        }
        res_admin_attempt = client.post("/api/v1/auth/register", json=admin_attempt_payload)
        assert res_admin_attempt.status_code == 200
        assert res_admin_attempt.json()["data"]["role"] == "user"

    app.dependency_overrides.clear()
