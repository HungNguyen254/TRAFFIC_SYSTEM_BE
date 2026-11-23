import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.user import User
from app.models.edge import Edge
from app.models.chat import ChatSession
from app.core.database import get_session
import app.core.database as db_mod
from app.core.security import create_access_token, hash_password
from app.core.crypto import (
    derive_user_master_key,
    encrypt_aes_gcm,
    decrypt_aes_gcm,
    encrypt_server_secret,
    generate_salt,
)
from app.services.prediction_service import PredictionService
from app.services.auth_service import AuthService
from app.schemas.auth import ChangePasswordRequest
from app.api.v1.endpoints.admin import _retrain_lock


@pytest.fixture(name="engine")
def engine_fixture():
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    old_engine = db_mod.engine
    db_mod.engine = test_engine
    yield test_engine
    db_mod.engine = old_engine


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture(name="client")
def client_fixture(session):
    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_edge_update_validation_rejects_zero_and_negative(client, session):
    admin = User(
        email="admin_val@test.vn",
        password_hash=hash_password("AdminPass123!"),
        full_name="Admin Val",
        role="admin",
        token_version=1,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)

    token = create_access_token({"sub": str(admin.user_id), "role": "admin", "token_version": 1})
    headers = {"Authorization": f"Bearer {token}"}
    fake_id = uuid.uuid4()
    
    resp_speed = client.put(f"/api/v1/edges/{fake_id}", json={"max_speed_limit": 0}, headers=headers)
    assert resp_speed.status_code == 422

    resp_len = client.put(f"/api/v1/edges/{fake_id}", json={"length_km": -5.0}, headers=headers)
    assert resp_len.status_code == 422


def test_get_edge_nonexistent_returns_404(client):
    fake_id = uuid.uuid4()
    resp = client.get(f"/api/v1/edges/{fake_id}")
    assert resp.status_code == 404
    assert resp.json()["status_code"] == 404


def test_weather_to_code_strict_matching():
    # 'stormy' and 'tornado' must NOT match 'to' (heavy rain = 2.0)
    assert PredictionService._weather_to_code("stormy") == 0.0
    assert PredictionService._weather_to_code("tornado") == 0.0
    assert PredictionService._weather_to_code("clear") == 0.0
    assert PredictionService._weather_to_code("sunny") == 0.0
    # Heavy rain keywords must return 2.0
    assert PredictionService._weather_to_code("mưa to") == 2.0
    assert PredictionService._weather_to_code("mua to") == 2.0
    assert PredictionService._weather_to_code("heavy rain") == 2.0
    assert PredictionService._weather_to_code("ngập") == 2.0
    # Normal rain returns 1.0
    assert PredictionService._weather_to_code("rain") == 1.0
    assert PredictionService._weather_to_code("mưa rào") == 1.0


def test_email_case_insensitivity(client, session):
    # Registration with uppercase
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": "CaseTest@Example.COM",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "full_name": "Case Test",
    })
    assert reg_resp.status_code == 200
    assert reg_resp.json()["data"]["email"] == "casetest@example.com"

    # Login with different casing succeeds
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "CASETEST@example.com",
        "password": "Password123!",
    })
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()["data"]

    # Duplicate registration with different case is rejected
    dup_resp = client.post("/api/v1/auth/register", json={
        "email": "casetest@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "full_name": "Case Duplicate",
    })
    assert dup_resp.status_code == 400


def test_change_password_rewraps_chat_session_key(session):
    user_salt = generate_salt()
    user = User(
        email="chat_rewrap@test.vn",
        password_hash=hash_password("OldPassword123!"),
        full_name="Chat Rewrap User",
        role="user",
        token_version=1,
        encryption_salt=user_salt,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # Simulate an active chat session with dual-envelope keys
    k_session = b"k_session_32_bytes_super_secret!"
    old_user_mk = derive_user_master_key("OldPassword123!", user_salt)
    enc_user_old, nonce_user_old = encrypt_aes_gcm(old_user_mk, k_session)
    enc_server, nonce_server = encrypt_server_secret(k_session)

    chat_session = ChatSession(
        user_id=user.user_id,
        session_key_enc_user=enc_user_old,
        session_key_nonce_user=nonce_user_old,
        session_key_enc_server=enc_server,
        session_key_nonce_server=nonce_server,
    )
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)

    # Perform change password
    AuthService.change_password(
        session,
        user,
        ChangePasswordRequest(
            current_password="OldPassword123!",
            new_password="NewPassword456!",
        ),
    )
    session.refresh(chat_session)

    # With the new password, user should be able to decrypt k_session!
    new_user_mk = derive_user_master_key("NewPassword456!", user_salt)
    decrypted_k_session = decrypt_aes_gcm(
        new_user_mk,
        chat_session.session_key_enc_user,
        chat_session.session_key_nonce_user,
    )
    assert decrypted_k_session == k_session


def test_retrain_lock_concurrency():
    assert not _retrain_lock.locked()
    acquired = _retrain_lock.acquire(blocking=False)
    assert acquired is True
    # Second acquisition fails
    second_acquire = _retrain_lock.acquire(blocking=False)
    assert second_acquire is False
    _retrain_lock.release()
