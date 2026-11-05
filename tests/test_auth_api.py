from fastapi.testclient import TestClient
from sqlmodel import Session


def test_register_user_success(client: TestClient):
    payload = {
        "username": "johndoe",
        "email": "john@example.com",
        "password": "mypassword123",
    }
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "johndoe"
    assert data["email"] == "john@example.com"
    assert data["role"] == "USER"
    assert "id" in data
    assert "hashed_password" not in data


def test_register_user_ignores_client_role(client: TestClient):
    # Attempt privilege escalation
    payload = {
        "username": "hacker",
        "email": "hacker@example.com",
        "password": "mypassword123",
        "role": "ADMIN",
    }
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "USER"  # Strictly USER


def test_register_duplicate_user(client: TestClient):
    payload = {
        "username": "uniqueuser",
        "email": "unique@example.com",
        "password": "mypassword123",
    }
    resp1 = client.post("/api/auth/register", json=payload)
    assert resp1.status_code == 201

    # Same username
    resp2 = client.post("/api/auth/register", json={
        "username": "uniqueuser",
        "email": "other@example.com",
        "password": "password456",
    })
    assert resp2.status_code == 400

    # Same email
    resp3 = client.post("/api/auth/register", json={
        "username": "otheruser",
        "email": "unique@example.com",
        "password": "password456",
    })
    assert resp3.status_code == 400


def test_login_json(client: TestClient):
    # Register first
    client.post("/api/auth/register", json={
        "username": "logintest",
        "email": "login@example.com",
        "password": "secretpassword",
    })

    # Login with JSON
    resp = client.post("/api/auth/login", json={
        "username": "logintest",
        "password": "secretpassword",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_form_data(client: TestClient):
    # Register first
    client.post("/api/auth/register", json={
        "username": "formtest",
        "email": "form@example.com",
        "password": "secretpassword",
    })

    # Login with form data (Swagger UI format)
    resp = client.post("/api/auth/login", data={
        "username": "formtest",
        "password": "secretpassword",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client: TestClient):
    resp_wrong_pw = client.post("/api/auth/login", json={
        "username": "logintest",
        "password": "wrong_password",
    })
    assert resp_wrong_pw.status_code == 401

    resp_unknown_user = client.post("/api/auth/login", json={
        "username": "non_existent_user",
        "password": "any_password",
    })
    assert resp_unknown_user.status_code == 401


def test_login_inactive_user(client: TestClient, session: Session):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    inactive_user = User(
        username="inactive_guy",
        email="inactive@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.USER,
        is_active=False,
    )
    session.add(inactive_user)
    session.commit()

    resp = client.post("/api/auth/login", json={
        "username": "inactive_guy",
        "password": "password123",
    })
    assert resp.status_code == 400
    assert "inactive" in resp.json()["detail"].lower()


def test_login_malformed_json(client: TestClient):
    resp = client.post(
        "/api/auth/login",
        content="invalid json content",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400



def test_get_current_user_me(client: TestClient):
    # Register & login
    client.post("/api/auth/register", json={
        "username": "metest",
        "email": "me@example.com",
        "password": "secretpassword",
    })
    login_resp = client.post("/api/auth/login", json={
        "username": "metest",
        "password": "secretpassword",
    })
    token = login_resp.json()["access_token"]

    # Call /api/auth/me with Bearer token
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    me_data = resp.json()
    assert me_data["username"] == "metest"
    assert me_data["email"] == "me@example.com"
    assert me_data["role"] == "USER"

    # Call /api/auth/me without token -> 401
    resp_no_token = client.get("/api/auth/me")
    assert resp_no_token.status_code == 401
