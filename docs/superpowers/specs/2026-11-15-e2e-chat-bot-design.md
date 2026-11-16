# Thiết Kế Kỹ Thuật: API Chatbot AI (Gemini API) với Mã Hóa E2E & Xác Thực Người Dùng (Đồng Bộ Đa Thiết Bị)

## 1. Tổng quan & Mục đích (Intent & Why)
Xây dựng hệ thống API Chatbot tích hợp Google Gemini API dành cho ứng dụng backend FastAPI. Hệ thống đáp ứng 3 tiêu chuẩn cốt lõi:
1. **Bảo mật truy cập (Authentication)**: Chỉ những người dùng đã đăng nhập (sở hữu JWT Token hợp lệ) mới có quyền tạo và tương tác với chatbot.
2. **Bảo mật đường truyền & Lưu trữ (Payload E2E & Zero-Knowledge at Rest)**: 
   - Tin nhắn giữa Client và Server được mã hóa payload (AES-256-GCM).
   - Server chỉ giải mã tạm thời trong RAM để chuyển tiếp prompt đến Gemini API.
   - Toàn bộ nội dung tin nhắn và tiêu đề lưu trong cơ sở dữ liệu đều là Ciphertext + Nonce. Server không lưu trữ plaintext hay khóa bí mật của người dùng trong cơ sở dữ liệu.
3. **Đồng bộ đa thiết bị (Cross-Device Synchronization)**: Người dùng có thể đăng nhập trên nhiều thiết bị khác nhau (laptop, điện thoại) và vẫn giải mã, đọc tiếp được toàn bộ lịch sử trò chuyện cũ nhờ cơ chế User Master Key dẫn xuất từ thông tin xác thực.

---

## 2. Mục tiêu, Phi mục tiêu & Ranh giới (Goals, Non-Goals, Anti-Goals)

### Mục tiêu (Goals):
- **Bảo vệ Endpoint bằng JWT**: Tích hợp chặt chẽ với hệ thống xác thực có sẵn (`get_current_user` trong `app/core/security.py`).
- **Quản lý khóa người dùng (User Salt & Master Key)**: Cung cấp endpoint cấp salt của user để client dẫn xuất `User Master Key` (PBKDF2/Argon2) trên mọi thiết bị khi đăng nhập.
- **Khởi tạo phiên chat (Handshake & Dual Envelope Session Key)**:
  - Client sinh khóa đối xứng phiên `K_session` (AES-256).
  - Client mã hóa `K_session` bằng `User Master Key` -> `session_key_enc_user` (để mọi thiết bị của user có thể khôi phục khóa phiên).
  - Client trao đổi khóa với Server qua ECDH X25519 để gửi an toàn `K_session` cho Server, hoặc Server mã hóa `K_session` bằng Server Master Secret -> `session_key_enc_server` (để Server giải mã trong RAM khi gọi Gemini).
- **Gửi tin nhắn mã hóa (Encrypted Messaging)**:
  - Client mã hóa payload `{"content": "..."}` bằng `K_session` (AES-256-GCM).
  - Server giải mã trong RAM, nạp ngữ cảnh lịch sử, gọi Google Gemini API, mã hóa phản hồi bằng `K_session`, lưu ciphertext vào DB và trả về cho Client.
- **Quản lý phiên & Tiêu đề**:
  - Hỗ trợ cập nhật tiêu đề mã hóa cho phiên (`PATCH /api/v1/chat/sessions/{session_id}`).
  - Lấy danh sách phiên (`GET /api/v1/chat/sessions`) trả kèm `session_key_enc_user` để thiết bị mới tải về và giải mã ngay lập tức.
  - Lấy lịch sử tin nhắn (`GET /api/v1/chat/sessions/{session_id}/messages`).
- **Tích hợp Gemini API**: Dịch vụ `GeminiService` gọi Google Gemini REST API qua `httpx.AsyncClient` với `GEMINI_API_KEY` và model cấu hình (mặc định `gemini-2.5-flash`).

### Phi mục tiêu (Non-Goals):
- Giao diện Frontend đầy đủ (cung cấp bộ test script demo client đầy đủ chu trình mã hóa/giải mã).
- Xử lý file/ảnh đa phương thức (multimodal) trong phiên bản này.

### Ranh giới nghiêm ngặt (Anti-Goals):
- Tuyệt đối **không** lưu trữ plaintext của prompt, câu trả lời, hay khóa bí mật chưa mã hóa của user trong cơ sở dữ liệu.
- Tuyệt đối **không** làm rò rỉ Gemini API Key về client.

---

## 3. Các ràng buộc kỹ thuật (Constraints)
- Python 3.12+, FastAPI, Pydantic v2, SQLModel (PostgreSQL/SQLite).
- Thư viện `cryptography`:
  - `X25519` cho trao đổi khóa ban đầu.
  - `AESGCM` (256-bit key, 12-byte nonce) cho mã hóa tin nhắn và khóa phiên.
  - `HKDF` / `PBKDF2HMAC` với `hashes.SHA256()` cho dẫn xuất khóa.
- Rate Limiting qua SlowAPI.

---

## 4. Kiến trúc Mật mã & Đồng bộ Đa thiết bị (Cryptographic Architecture)

```
[Device A]                                         [Server]                                   [Device B]
    |                                                 |                                           |
    |-- 1. Login -> Nhận JWT & User Salt              |                                           |
    |-- 2. Dẫn xuất User Master Key (UMK)             |                                           |
    |                                                 |                                           |
    |-- 3. Tạo Session:                               |                                           |
    |      Sinh K_session (AES-256)                   |                                           |
    |      Encrypt K_session bằng UMK -> enc_user     |                                           |
    |      Handshake ECDH X25519 với Server --------> |                                           |
    |                                                 |-- Lưu session_key_enc_server              |
    |                                                 |-- Lưu session_key_enc_user                |
    |                                                 |                                           |
    |-- 4. Gửi message (AES-GCM với K_session) -----> |-- RAM: decrypt message                    |
    |                                                 |-- Gọi Gemini API                          |
    |                                                 |-- RAM: encrypt response                   |
    |<-- Trả về response (AES-GCM) -------------------|-- Lưu ciphertext tin nhắn vào DB           |
    |                                                 |                                           |
    |                                                 |                                           |-- 5. Login từ Device B
    |                                                 |                                           |-- 6. Dẫn xuất UMK từ password
    |                                                 |<-- 7. GET /sessions ----------------------|
    |                                                 |--- Trả về list kèm enc_user ------------->|
    |                                                 |                                           |-- 8. Decrypt enc_user bằng UMK
    |                                                 |                                           |      -> Khôi phục K_session!
    |                                                 |<-- 9. GET /messages ----------------------|
    |                                                 |--- Trả về ciphertext -------------------->|
    |                                                 |                                           |-- 10. Decrypt tin nhắn cũ!
```

---

## 5. Thiết kế Chi tiết Thành phần (Detailed Design)

### 5.1. Mô hình Dữ liệu (Database Models)

```python
# app/models/chat.py
import uuid
from datetime import UTC, datetime
from sqlmodel import Field, SQLModel
import sqlalchemy as sa

class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_sessions"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(sa.Uuid, primary_key=True, nullable=False),
    )
    user_id: uuid.UUID = Field(
        sa_column=sa.Column(sa.Uuid, sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    )
    title_encrypted: str | None = Field(default=None)   # Base64 ciphertext của tiêu đề
    title_nonce: str | None = Field(default=None)       # Base64 12-byte nonce của tiêu đề
    
    # Khóa phiên được bọc 2 lớp (Dual Envelope):
    session_key_enc_user: str = Field(nullable=False)   # K_session mã hóa bằng User Master Key (base64)
    session_key_nonce_user: str = Field(nullable=False) # Nonce base64 tương ứng
    session_key_enc_server: str = Field(nullable=False) # K_session mã hóa bằng Server App Secret (base64)
    session_key_nonce_server: str = Field(nullable=False)# Nonce base64 tương ứng

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(sa.Uuid, primary_key=True, nullable=False),
    )
    session_id: uuid.UUID = Field(
        sa_column=sa.Column(sa.Uuid, sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    role: str = Field(max_length=20)                    # "user" hoặc "model"
    ciphertext: str = Field(nullable=False)             # Base64 encrypted payload
    nonce: str = Field(nullable=False)                  # Base64 12-byte nonce
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

Bổ sung trường `encryption_salt` vào `User` model (nếu chưa có) để làm muối dẫn xuất User Master Key đồng nhất trên mọi thiết bị của user.

### 5.2. Định dạng Payload Nội bộ (Inner Payload Schema)
Mọi dữ liệu bên trong ciphertext đều chuẩn hóa JSON:
```json
// Nội dung gửi và nhận đều thống nhất cấu trúc:
{
  "content": "Nội dung văn bản tin nhắn",
  "timestamp": "2026-11-15T10:30:00Z"
}
```
Khi gặp lỗi hệ thống (như Gemini quota, invalid key), Server trả về mã lỗi HTTP chuẩn (400, 429, 502) với schema lỗi chung của ứng dụng: `{"success": false, "message": "Chi tiết lỗi", "data": null}`.

### 5.3. Danh sách Endpoint API

| Phương thức | Đường dẫn | Xác thực | Chức năng |
|---|---|---|---|
| `GET` | `/api/v1/chat/user-salt` | JWT Bearer | Lấy `encryption_salt` của user để client dẫn xuất User Master Key |
| `POST` | `/api/v1/chat/handshake` | JWT Bearer | Khởi tạo session: trao đổi public key X25519 để chuyển `K_session` an toàn lên Server |
| `POST` | `/api/v1/chat/message` | JWT Bearer | Gửi tin nhắn mã hóa (prompt), server gọi Gemini và trả về câu trả lời mã hóa |
| `GET` | `/api/v1/chat/sessions` | JWT Bearer | Danh sách phiên chat (kèm `session_key_enc_user` để thiết bị giải mã) |
| `PATCH` | `/api/v1/chat/sessions/{session_id}` | JWT Bearer | Cập nhật tiêu đề phiên chat (`title_encrypted`, `title_nonce`) |
| `GET` | `/api/v1/chat/sessions/{session_id}/messages` | JWT Bearer | Lấy toàn bộ lịch sử tin nhắn mã hóa trong phiên |
| `DELETE` | `/api/v1/chat/sessions/{session_id}` | JWT Bearer | Xóa phiên chat và toàn bộ tin nhắn liên quan |

### 5.4. Dịch vụ Gemini (GeminiService)
- Cấu hình qua `app/core/config.py`:
  - `GEMINI_API_KEY: str = ""`
  - `GEMINI_MODEL: str = "gemini-2.5-flash"`
- Service `app/services/gemini_service.py`:
  - Gọi Google Gemini endpoint: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}`.
  - Quản lý hội thoại đa lượt (multi-turn history) với định dạng chuẩn của Gemini:
    ```json
    {
      "contents": [
        {"role": "user", "parts": [{"text": "..."}]},
        {"role": "model", "parts": [{"text": "..."}]}
      ]
    }
    ```
  - Xử lý timeout và trả về lỗi thân thiện nếu không cấu hình API Key.

---

## 6. Phân công cho Builder (What's Left to the Builder)
- Tự động tạo `encryption_salt` cho User nếu người dùng cũ chưa có.
- Cung cấp script client mẫu `scripts/chat_e2e_client_demo.py` thực hiện đầy đủ luồng:
  1. Đăng nhập lấy JWT và User Salt.
  2. Dẫn xuất User Master Key trên client.
  3. Tạo session và bắt tay bảo mật với backend.
  4. Mã hóa prompt, gửi request đến `/api/v1/chat/message`.
  5. Nhận response, giải mã câu trả lời từ Gemini.
  6. Mô phỏng Device B đăng nhập, tải lịch sử phiên, giải mã `session_key_enc_user` và đọc lại tin nhắn cũ.
- Viết unit test & integration test bao phủ toàn bộ luồng mật mã và API endpoints.
