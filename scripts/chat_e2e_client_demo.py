"""Demo Script: E2E Encrypted Chatbot Client Simulation.

This script demonstrates:
1. User Authentication (JWT Login)
2. Client-side User Master Key (UMK) Derivation via PBKDF2
3. Ephemeral ECDH X25519 Handshake & AES-256-GCM Session Key Agreement
4. End-to-End Encrypted Prompt Transmission and Response Decryption
5. Multi-Device Synchronization (Device B decrypts history using password)
"""

import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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


def run_demo():
    print("=" * 70)
    print("      DEMO CLIENT: CHATBOT AI VỚI MÃ HÓA ĐẦU CUỐI (E2E) & ĐỒNG BỘ ĐA THIẾT BỊ      ")
    print("=" * 70)

    # 0. Setup in-memory DB for the demo
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)

    # Mock GeminiService so the demo runs standalone without requiring external network
    async def mock_generate_response(self, contents, system_instruction=None):
        last_user_text = contents[-1]["parts"][0]["text"]
        return f"[Gemini 2.5 Flash Response]: Tôi đã nhận và giải mã thành công câu hỏi: '{last_user_text}'"

    GeminiService.generate_response = mock_generate_response

    # Register user
    email = "demo_user@example.com"
    password = "MySecurePassword123@"
    with Session(engine) as session:
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name="Nguyễn Văn Demo",
            role="user",
            token_version=1,
        )
        session.add(user)
        session.commit()

    print("\n[BƯỚC 1: DEVICE A - ĐĂNG NHẬP VÀ XÁC THỰC]")
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["data"]["access_token"]
    headers_a = {"Authorization": f"Bearer {token}"}
    print(f" -> Đăng nhập thành công! JWT Token: {token[:24]}...")

    print("\n[BƯỚC 2: DEVICE A - LẤY USER SALT & DẪN XUẤT USER MASTER KEY]")
    salt_res = client.get("/api/v1/chat/user-salt", headers=headers_a).json()["data"]
    salt = salt_res["encryption_salt"]
    server_pub_b64 = salt_res["server_public_key"]
    print(f" -> User Salt: {salt}")
    print(f" -> Server X25519 Public Key: {server_pub_b64}")

    umk_a = derive_user_master_key(password, salt)
    print(f" -> User Master Key (UMK) dẫn xuất thành công (32 bytes trong RAM)!")

    print("\n[BƯỚC 3: DEVICE A - KHỞI TẠO PHIÊN & HANDSHAKE ECDH X25519]")
    client_priv, client_pub_b64 = generate_x25519_keypair()
    shared_secret = derive_shared_secret(client_priv, server_pub_b64)
    k_session = derive_key_hkdf(
        shared_secret=shared_secret,
        salt=b"traffic-chat-session",
        info=b"session-symmetric-key",
        length=32,
    )

    # Bọc K_session bằng UMK để lưu vào DB phục vụ đồng bộ đa thiết bị
    enc_k_session_user, nonce_k_session_user = encrypt_aes_gcm(umk_a, k_session)

    handshake_res = client.post(
        "/api/v1/chat/handshake",
        json={
            "client_public_key": client_pub_b64,
            "session_key_enc_user": enc_k_session_user,
            "session_key_nonce_user": nonce_k_session_user,
        },
        headers=headers_a,
    ).json()["data"]
    session_id = handshake_res["session_id"]
    print(f" -> Bắt tay thành công! Session ID: {session_id}")
    print(f" -> Khóa đối xứng phiên (K_session) được hai bên tính toán đồng nhất!")

    print("\n[BƯỚC 4: DEVICE A - GỬI TIN NHẮN MÃ HÓA ĐẦU CUỐI]")
    prompt = "Tình hình giao thông tại ngã tư Hàng Xanh hiện tại như thế nào?"
    print(f" -> Prompt gốc (Plaintext): '{prompt}'")

    # Mã hóa AES-256-GCM
    prompt_json = json.dumps({"content": prompt}).encode("utf-8")
    ct_prompt, nonce_prompt = encrypt_aes_gcm(k_session, prompt_json)
    print(f" -> Gửi lên Server Ciphertext: {ct_prompt[:32]}... (Nonce: {nonce_prompt})")

    # Gửi qua API
    msg_res = client.post(
        "/api/v1/chat/message",
        json={"session_id": session_id, "ciphertext": ct_prompt, "nonce": nonce_prompt},
        headers=headers_a,
    ).json()["data"]

    # Nhận phản hồi mã hóa
    ai_ct = msg_res["ciphertext"]
    ai_nonce = msg_res["nonce"]
    print(f" -> Server trả về Ciphertext: {ai_ct[:32]}... (Nonce: {ai_nonce})")

    # Giải mã phản hồi
    ai_pt_bytes = decrypt_aes_gcm(k_session, ai_ct, ai_nonce)
    ai_reply = json.loads(ai_pt_bytes.decode("utf-8"))["content"]
    print(f" -> [DEVICE A] Đã giải mã câu trả lời của AI: '{ai_reply}'")

    print("\n" + "-" * 70)
    print("[BƯỚC 5: MÔ PHỎNG DEVICE B - ĐỒNG BỘ ĐA THIẾT BỊ]")
    print("Device B đăng nhập bằng tài khoản và mật khẩu, tải lịch sử tin nhắn:")

    login_b = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["data"]
    headers_b = {"Authorization": f"Bearer {login_b['access_token']}"}

    salt_b = client.get("/api/v1/chat/user-salt", headers=headers_b).json()["data"]["encryption_salt"]
    umk_b = derive_user_master_key(password, salt_b)

    sessions_b = client.get("/api/v1/chat/sessions", headers=headers_b).json()["data"]
    target_session = sessions_b[0]

    # Device B khôi phục K_session bằng UMK của mình
    recovered_k_session = decrypt_aes_gcm(
        umk_b,
        target_session["session_key_enc_user"],
        target_session["session_key_nonce_user"],
    )
    print(" -> Device B đã giải mã thành công K_session từ Server!")

    # Tải và giải mã toàn bộ lịch sử
    messages_b = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=headers_b).json()["data"]
    print(f" -> Device B tải được {len(messages_b)} tin nhắn mã hóa từ DB:")

    for idx, m in enumerate(messages_b, 1):
        pt = json.loads(decrypt_aes_gcm(recovered_k_session, m["ciphertext"], m["nonce"]).decode("utf-8"))
        print(f"    [{idx}] Role '{m['role']}': {pt['content']}")

    print("\n" + "=" * 70)
    print("      DEMO HOÀN TẤT THÀNH CÔNG: E2E MÃ HÓA + BẢO MẬT DB + SYNC ĐA THIẾT BỊ!      ")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
