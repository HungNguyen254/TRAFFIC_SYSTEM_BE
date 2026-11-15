import json
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.main import app
from app.core.database import get_session
from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.core.crypto import (
    generate_x25519_keypair,
    derive_shared_secret,
    derive_key_hkdf,
    derive_user_master_key,
    encrypt_aes_gcm,
    decrypt_aes_gcm,
)
from app.services.gemini_service import GeminiService


from sqlalchemy.pool import StaticPool

@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="db_session")
def db_session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(engine):
    def get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(name="auth_headers")
def auth_headers_fixture(db_session: Session):
    user = User(
        email="alice@example.com",
        password_hash=hash_password("Password123!"),
        full_name="Alice Crypto",
        role="user",
        token_version=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token({"sub": str(user.user_id), "token_version": user.token_version})
    return {"Authorization": f"Bearer {token}"}, user


def test_chat_endpoints_require_authentication(client: TestClient):
    response = client.get("/api/v1/chat/user-salt")
    assert response.status_code == 401

    response = client.post("/api/v1/chat/handshake", json={})
    assert response.status_code == 401

    response = client.post("/api/v1/chat/message", json={})
    assert response.status_code == 401

    response = client.get("/api/v1/chat/sessions")
    assert response.status_code == 401


def test_get_user_salt_and_server_public_key(client: TestClient, auth_headers):
    headers, user = auth_headers
    response = client.get("/api/v1/chat/user-salt", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["encryption_salt"] == user.encryption_salt
    assert "server_public_key" in data
    assert len(data["server_public_key"]) > 20


def test_full_e2e_chat_flow(client: TestClient, auth_headers, monkeypatch, db_session: Session):
    headers, user = auth_headers

    # 1. Get user salt & server public key
    salt_resp = client.get("/api/v1/chat/user-salt", headers=headers).json()["data"]
    user_salt = salt_resp["encryption_salt"]
    server_pub_b64 = salt_resp["server_public_key"]

    # 2. Derive User Master Key
    umk = derive_user_master_key("Password123!", user_salt)

    # 3. Client creates X25519 keypair and derives K_session
    client_priv, client_pub_b64 = generate_x25519_keypair()
    shared_secret = derive_shared_secret(client_priv, server_pub_b64)
    k_session = derive_key_hkdf(
        shared_secret=shared_secret,
        salt=b"traffic-chat-session",
        info=b"session-symmetric-key",
        length=32,
    )

    # 4. Client encrypts K_session with UMK
    enc_key_user, nonce_key_user = encrypt_aes_gcm(umk, k_session)

    # 5. Handshake
    handshake_payload = {
        "client_public_key": client_pub_b64,
        "session_key_enc_user": enc_key_user,
        "session_key_nonce_user": nonce_key_user,
    }
    handshake_resp = client.post("/api/v1/chat/handshake", json=handshake_payload, headers=headers)
    assert handshake_resp.status_code == 200
    session_data = handshake_resp.json()["data"]
    session_id = session_data["session_id"]
    assert session_id is not None

    # 6. Mock GeminiService
    async def mock_generate_response(self, contents, system_instruction=None):
        return "Chào bạn, tôi là trợ lý AI."

    monkeypatch.setattr(GeminiService, "generate_response", mock_generate_response)

    # 7. Encrypt and send user message
    user_msg_json = json.dumps({"content": "Xin chào AI!"}).encode("utf-8")
    msg_ciphertext, msg_nonce = encrypt_aes_gcm(k_session, user_msg_json)

    msg_payload = {
        "session_id": session_id,
        "ciphertext": msg_ciphertext,
        "nonce": msg_nonce,
    }
    msg_resp = client.post("/api/v1/chat/message", json=msg_payload, headers=headers)
    assert msg_resp.status_code == 200
    reply_data = msg_resp.json()["data"]
    assert reply_data["session_id"] == session_id

    # 8. Decrypt AI response
    reply_bytes = decrypt_aes_gcm(k_session, reply_data["ciphertext"], reply_data["nonce"])
    reply_obj = json.loads(reply_bytes.decode("utf-8"))
    assert reply_obj["content"] == "Chào bạn, tôi là trợ lý AI."

    # 9. Verify zero-knowledge at rest in DB: no plaintext prompt or AI response in DB
    db_messages = db_session.exec(select(ChatMessage).where(ChatMessage.session_id == uuid.UUID(session_id))).all()
    assert len(db_messages) == 2
    for m in db_messages:
        assert "Xin chào" not in m.ciphertext
        assert "trợ lý AI" not in m.ciphertext

    # 10. Update title
    title_bytes = json.dumps({"content": "Hội thoại chào hỏi"}).encode("utf-8")
    title_ct, title_nonce = encrypt_aes_gcm(k_session, title_bytes)
    patch_resp = client.patch(
        f"/api/v1/chat/sessions/{session_id}",
        json={"title_encrypted": title_ct, "title_nonce": title_nonce},
        headers=headers,
    )
    assert patch_resp.status_code == 200

    # 11. Fetch sessions
    sessions_resp = client.get("/api/v1/chat/sessions", headers=headers)
    assert sessions_resp.status_code == 200
    sessions_list = sessions_resp.json()["data"]
    assert len(sessions_list) == 1
    assert sessions_list[0]["id"] == session_id
    assert sessions_list[0]["session_key_enc_user"] == enc_key_user

    # 12. Fetch messages
    messages_resp = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=headers)
    assert messages_resp.status_code == 200
    messages_list = messages_resp.json()["data"]
    assert len(messages_list) == 2

    # 13. Delete session
    delete_resp = client.delete(f"/api/v1/chat/sessions/{session_id}", headers=headers)
    assert delete_resp.status_code == 200

    # Verify deleted in DB
    assert client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=headers).status_code == 404


def test_cross_user_isolation(client: TestClient, auth_headers, db_session: Session):
    headers_alice, user_alice = auth_headers

    # Create User Bob
    user_bob = User(
        email="bob@example.com",
        password_hash=hash_password("Password123!"),
        full_name="Bob Crypto",
        role="user",
        token_version=1,
    )
    db_session.add(user_bob)
    db_session.commit()
    db_session.refresh(user_bob)
    token_bob = create_access_token({"sub": str(user_bob.user_id), "token_version": user_bob.token_version})
    headers_bob = {"Authorization": f"Bearer {token_bob}"}

    # Alice creates a session
    salt_resp = client.get("/api/v1/chat/user-salt", headers=headers_alice).json()["data"]
    client_priv, client_pub = generate_x25519_keypair()
    handshake_resp = client.post(
        "/api/v1/chat/handshake",
        json={
            "client_public_key": client_pub,
            "session_key_enc_user": "fake_enc_user",
            "session_key_nonce_user": "fake_nonce",
        },
        headers=headers_alice,
    )
    alice_session_id = handshake_resp.json()["data"]["session_id"]

    # Bob tries to access Alice's session -> must return 404 or 403
    assert client.get(f"/api/v1/chat/sessions/{alice_session_id}/messages", headers=headers_bob).status_code == 404
    assert client.delete(f"/api/v1/chat/sessions/{alice_session_id}", headers=headers_bob).status_code == 404
    assert client.patch(f"/api/v1/chat/sessions/{alice_session_id}", json={}, headers=headers_bob).status_code == 404


def test_nonce_reuse_and_tampered_ciphertext_and_isolation(client: TestClient, auth_headers, monkeypatch, db_session: Session):
    headers, user = auth_headers

    salt_resp = client.get("/api/v1/chat/user-salt", headers=headers).json()["data"]
    client_priv, client_pub = generate_x25519_keypair()
    shared_secret = derive_shared_secret(client_priv, salt_resp["server_public_key"])
    k_session = derive_key_hkdf(shared_secret, salt=b"traffic-chat-session", info=b"session-symmetric-key", length=32)

    handshake_resp = client.post(
        "/api/v1/chat/handshake",
        json={
            "client_public_key": client_pub,
            "session_key_enc_user": "dummy_enc",
            "session_key_nonce_user": "dummy_nonce",
        },
        headers=headers,
    )
    session_id = handshake_resp.json()["data"]["session_id"]

    async def mock_ai(self, contents, system_instruction=None):
        return "AI reply"

    monkeypatch.setattr(GeminiService, "generate_response", mock_ai)

    ct, nonce = encrypt_aes_gcm(k_session, json.dumps({"content": "First msg"}).encode("utf-8"))

    # 1. Send first message -> 200
    res1 = client.post("/api/v1/chat/message", json={"session_id": session_id, "ciphertext": ct, "nonce": nonce}, headers=headers)
    assert res1.status_code == 200

    # 2. Replay/Reuse same nonce -> MUST FAIL 400
    res_reuse = client.post("/api/v1/chat/message", json={"session_id": session_id, "ciphertext": ct, "nonce": nonce}, headers=headers)
    assert res_reuse.status_code == 400
    assert "Nonce" in res_reuse.json()["message"]

    # 3. Tampered ciphertext -> MUST FAIL 400
    import base64
    raw_ct = bytearray(base64.b64decode(ct))
    raw_ct[0] ^= 0xFF
    bad_ct = base64.b64encode(raw_ct).decode("utf-8")
    new_nonce = base64.b64encode(b"0" * 12).decode("utf-8")
    res_tamper = client.post("/api/v1/chat/message", json={"session_id": session_id, "ciphertext": bad_ct, "nonce": new_nonce}, headers=headers)
    assert res_tamper.status_code == 400

    # 4. User B tries to post message to Alice's session -> MUST FAIL 404
    user_b = User(
        email="bob_attacker@example.com",
        password_hash=hash_password("Pass123!"),
        full_name="Bob Attacker",
        role="user",
        token_version=1,
    )
    db_session.add(user_b)
    db_session.commit()
    db_session.refresh(user_b)
    token_bob = create_access_token({"sub": str(user_b.user_id), "token_version": user_b.token_version})
    res_bob_post = client.post("/api/v1/chat/message", json={"session_id": session_id, "ciphertext": ct, "nonce": new_nonce}, headers={"Authorization": f"Bearer {token_bob}"})
    assert res_bob_post.status_code == 404

    # 5. Non-dict payload (e.g. JSON array) -> MUST FAIL 400
    array_ct, array_nonce = encrypt_aes_gcm(k_session, json.dumps(["invalid", "payload"]).encode("utf-8"))
    res_array = client.post("/api/v1/chat/message", json={"session_id": session_id, "ciphertext": array_ct, "nonce": array_nonce}, headers=headers)
    assert res_array.status_code == 400
