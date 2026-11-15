import json
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_session
from app.core.security import hash_password
from app.models.user import User
from app.core.crypto import (
    generate_x25519_keypair,
    derive_shared_secret,
    derive_key_hkdf,
    derive_user_master_key,
    encrypt_aes_gcm,
    decrypt_aes_gcm,
)
from app.services.gemini_service import GeminiService


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="client")
def client_fixture(engine):
    def get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_cross_device_session_sync_and_e2e_decryption(client: TestClient, engine, monkeypatch):
    password = "SuperSecurePassword2026!"
    email = "device_user@example.com"

    # Setup User in DB
    with Session(engine) as session:
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name="Multi Device User",
            role="user",
            token_version=1,
        )
        session.add(user)
        session.commit()

    # Mock GeminiService
    async def mock_generate_response(self, contents, system_instruction=None):
        return "Chào Device A! Tôi ghi nhận câu hỏi của bạn."

    monkeypatch.setattr(GeminiService, "generate_response", mock_generate_response)

    # ==================== DEVICE A ====================
    # 1. Device A: Đăng nhập
    login_resp_a = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp_a.status_code == 200
    token_a = login_resp_a.json()["data"]["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Device A: Lấy salt và server public key
    salt_resp_a = client.get("/api/v1/chat/user-salt", headers=headers_a).json()["data"]
    salt = salt_resp_a["encryption_salt"]
    server_pub_b64 = salt_resp_a["server_public_key"]

    # 3. Device A: Dẫn xuất User Master Key (UMK)
    umk_a = derive_user_master_key(password, salt)

    # 4. Device A: Trao đổi khóa X25519 & tính K_session
    client_priv_a, client_pub_a = generate_x25519_keypair()
    shared_secret_a = derive_shared_secret(client_priv_a, server_pub_b64)
    k_session_a = derive_key_hkdf(
        shared_secret=shared_secret_a,
        salt=b"traffic-chat-session",
        info=b"session-symmetric-key",
        length=32,
    )

    # 5. Device A: Mã hóa K_session bằng UMK của user
    enc_k_session_user, nonce_k_session_user = encrypt_aes_gcm(umk_a, k_session_a)

    # 6. Device A: Handshake tạo session
    handshake_resp_a = client.post(
        "/api/v1/chat/handshake",
        json={
            "client_public_key": client_pub_a,
            "session_key_enc_user": enc_k_session_user,
            "session_key_nonce_user": nonce_k_session_user,
        },
        headers=headers_a,
    )
    assert handshake_resp_a.status_code == 200
    session_id = handshake_resp_a.json()["data"]["session_id"]

    # 7. Device A: Gửi tin nhắn mã hóa
    user_prompt = "Đây là thông tin mật gửi từ Laptop Device A!"
    ct_a, nonce_a = encrypt_aes_gcm(k_session_a, json.dumps({"content": user_prompt}).encode("utf-8"))
    msg_resp_a = client.post(
        "/api/v1/chat/message",
        json={"session_id": session_id, "ciphertext": ct_a, "nonce": nonce_a},
        headers=headers_a,
    )
    assert msg_resp_a.status_code == 200

    # Device A nhận câu trả lời và giải mã
    reply_data_a = msg_resp_a.json()["data"]
    reply_pt_a = decrypt_aes_gcm(k_session_a, reply_data_a["ciphertext"], reply_data_a["nonce"])
    assert json.loads(reply_pt_a.decode("utf-8"))["content"] == "Chào Device A! Tôi ghi nhận câu hỏi của bạn."

    # ==================== DEVICE B ====================
    # Device B là một thiết bị mới hoàn toàn (chỉ có username + password của người dùng)
    # 1. Device B: Đăng nhập
    login_resp_b = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp_b.status_code == 200
    token_b = login_resp_b.json()["data"]["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 2. Device B: Lấy salt của user
    salt_resp_b = client.get("/api/v1/chat/user-salt", headers=headers_b).json()["data"]
    assert salt_resp_b["encryption_salt"] == salt

    # 3. Device B: Dẫn xuất User Master Key (UMK) từ password của user
    umk_b = derive_user_master_key(password, salt_resp_b["encryption_salt"])
    assert umk_b == umk_a  # Cả 2 thiết bị tính ra cùng UMK

    # 4. Device B: Tải danh sách phiên chat
    sessions_resp_b = client.get("/api/v1/chat/sessions", headers=headers_b)
    assert sessions_resp_b.status_code == 200
    sessions_b = sessions_resp_b.json()["data"]
    assert len(sessions_b) == 1
    session_item_b = sessions_b[0]
    assert session_item_b["id"] == session_id

    # 5. Device B: Giải mã K_session bằng UMK của mình!
    recovered_k_session_b = decrypt_aes_gcm(
        umk_b,
        session_item_b["session_key_enc_user"],
        session_item_b["session_key_nonce_user"],
    )
    assert recovered_k_session_b == k_session_a  # K_session đã được khôi phục trên Device B!

    # 6. Device B: Lấy toàn bộ lịch sử tin nhắn của phiên chat
    messages_resp_b = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=headers_b)
    assert messages_resp_b.status_code == 200
    messages_b = messages_resp_b.json()["data"]
    assert len(messages_b) == 2

    # 7. Device B: Giải mã từng tin nhắn bằng K_session vừa khôi phục
    decrypted_msg_1 = json.loads(decrypt_aes_gcm(recovered_k_session_b, messages_b[0]["ciphertext"], messages_b[0]["nonce"]).decode("utf-8"))
    decrypted_msg_2 = json.loads(decrypt_aes_gcm(recovered_k_session_b, messages_b[1]["ciphertext"], messages_b[1]["nonce"]).decode("utf-8"))

    assert decrypted_msg_1["content"] == user_prompt
    assert decrypted_msg_2["content"] == "Chào Device A! Tôi ghi nhận câu hỏi của bạn."
