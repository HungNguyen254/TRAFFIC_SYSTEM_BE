# Design Document: Authentication, RBAC & Segment CRUD

- **Date:** 2026-11-05
- **Status:** Proposed
- **Author:** Antigravity & User

---

## 1. Intent & The Why
Hệ thống hiện tại chưa có cơ chế định danh và phân quyền người dùng; bất kỳ ai cũng có thể gọi endpoint tạo mới đoạn đường (`POST /api/segments`), đồng thời các thao tác cập nhật và xóa đoạn đường (`PUT`, `DELETE`) chưa được hiện thực.
Thiết kế này bổ sung hệ thống Xác thực (Authentication) dựa trên JWT Bearer Token và Phân quyền theo vai trò (Role-Based Access Control - RBAC):
- Vai trò **Admin**: Toàn quyền thêm, xem, sửa, xóa (CRUD) các đoạn đường trong hệ thống.
- Vai trò **User**: Người dùng thông thường chỉ có quyền xem (Read-only) danh sách đoạn đường và lịch sử quan trắc.

---

## 2. Goals, Non-Goals, and Anti-Goals

### Goals
- Xây dựng model SQLModel `User` (`app/models/user.py`) lưu thông tin tài khoản với các trường: `id`, `username`, `email`, `hashed_password`, `role` (enum `"ADMIN"`, `"USER"`), `is_active`, `created_at`.
- Tạo migration Alembic cập nhật cơ sở dữ liệu với bảng `user`.
- Cung cấp module bảo mật (`app/core/security.py`):
  - Băm và kiểm tra mật khẩu sử dụng `hashlib.pbkdf2_hmac` kết hợp salt ngẫu nhiên (sử dụng thư viện chuẩn của Python, an toàn tuyệt đối và tương thích 100% với Python 3.14).
  - Tạo và giải mã JWT Access Token với thuật toán `HS256`, cấu hình thời hạn hết hạn (mặc định 60 phút) và secret key qua `Settings`.
- Cung cấp các dependency xác thực trong FastAPI:
  - `get_current_user`: Trích xuất token từ header `Authorization: Bearer <token>`, giải mã và truy vấn DB; trả về 401 nếu token không hợp lệ hoặc hết hạn.
  - `require_admin`: Kế thừa `get_current_user`, kiểm tra `user.role == "ADMIN"`; trả về 403 Forbidden nếu user không có quyền quản trị.
- Các endpoints xác thực (`/api/auth`):
  - `POST /api/auth/register`: Đăng ký tài khoản mới (mặc định role `"USER"`).
  - `POST /api/auth/login`: Đăng nhập bằng `username` và `password`, trả về JWT `access_token` và `token_type: "bearer"`.
  - `GET /api/auth/me`: Lấy thông tin tài khoản đang đăng nhập.
- Hoàn thiện đầy đủ bộ CRUD cho đoạn đường (`app/api/segments.py`):
  - `GET /api/segments` & `GET /api/segments/{id}`: Yêu cầu đăng nhập (`USER` hoặc `ADMIN`).
  - `POST /api/segments`: Yêu cầu quyền `ADMIN` (tạo mới đoạn đường, trả về 201).
  - `PUT /api/segments/{id}`: Yêu cầu quyền `ADMIN` (cập nhật thông tin đoạn đường, trả về 200; 404 nếu không tìm thấy).
  - `DELETE /api/segments/{id}`: Yêu cầu quyền `ADMIN` (xóa đoạn đường và các quan trắc liên quan, trả về 200 hoặc 204; 404 nếu không tìm thấy).
  - `GET /api/segments/{id}/history`: Yêu cầu đăng nhập (`USER` hoặc `ADMIN`).
- Cập nhật script seed (`scripts/seed_demo.py`) tự động tạo 1 tài khoản Admin mặc định (`admin / admin123`) và 1 tài khoản User (`user / user123`).
- Bộ test suite Pytest kiểm thử toàn diện: đăng ký, đăng nhập, 401 khi thiếu/sai token, 403 khi User cố tình thêm/sửa/xóa, và 200/201/204 khi Admin thực hiện CRUD.

### Non-Goals
- Không xây dựng OAuth2 mạng xã hội (Google, Facebook).
- Không xây dựng quy trình gửi email reset mật khẩu.
- Không xây dựng refresh token rotation phức tạp.

### Anti-Goals
- Tuyệt đối không lưu mật khẩu dạng plain-text trong cơ sở dữ liệu.
- Không để xảy ra tình trạng User thông thường có thể vượt quyền gọi POST/PUT/DELETE trên segments (bắt buộc chặn ở tầng dependency `require_admin` với mã 403).
- Không để xảy ra lỗi Foreign Key Constraint khi Admin xóa một đoạn đường đang có liên kết với bảng `trafficobservation`.

---

## 3. Constraints
- **Môi trường**: Python 3.14+, FastAPI, SQLModel.
- **Dependencies**: Chỉ thêm `pyjwt` (cho việc mã hóa/giải mã JWT). Mật khẩu được băm bằng `hashlib.pbkdf2_hmac` từ Python standard library để tránh xung đột thư viện `passlib`/`crypt` trên Python 3.14.
- **Portability**: Truy vấn SQLModel portable trên cả SQLite và PostgreSQL.

---

## 4. Approaches Considered

1. **Phương án 1 (Đã chọn): JWT Bearer Token (Stateless)**
   - *Mô tả*: Server cấp token JWT có chữ ký điện tử chứa `sub` (user_id), `username`, và `role`. Client gửi token trong header `Authorization: Bearer <token>`.
   - *Ưu điểm*: Chuẩn mực ngành cho SPA (Vite/React) kết nối FastAPI, không tốn tài nguyên quản lý session ở DB, dễ mở rộng và kiểm thử.
   - *Lý do chọn*: Phù hợp nhất với ngữ cảnh frontend Vite đã nêu trong tài liệu dự án.

2. **Phương án 2: Session Cookie (Stateful)**
   - *Mô tả*: Lưu session trong bảng DB, gửi session cookie.
   - *Nhược điểm*: Phải cấu hình CORS phức tạp giữa Vite dev (`localhost:5173`) và backend (`localhost:8000`), tốn truy vấn DB quản lý bảng session.

---

## 5. Detailed Design

### 5.1. Data Model (`app/models/user.py`)
```python
from enum import Enum
from typing import Optional
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlmodel import Field, SQLModel

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    USER = "USER"

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    role: UserRole = Field(default=UserRole.USER)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None), sa_type=sa.DateTime)
```

### 5.2. Security Module (`app/core/security.py`)
- `hash_password(password: str) -> str`: Tạo salt 16-byte ngẫu nhiên qua `secrets.token_hex(16)`, băm bằng `hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)`, lưu định dạng `f"{salt}${hashed_hex}"`.
- `verify_password(password: str, hashed_password: str) -> bool`: Tách salt và hash cũ, băm lại password với salt đó và so sánh bằng `hmac.compare_digest`.
- `create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str`: Sinh JWT ký bằng `settings.JWT_SECRET_KEY` qua thuật toán `HS256`.
- `decode_access_token(token: str) -> dict`: Giải mã token, kiểm tra hạn sử dụng và tính hợp lệ.

### 5.3. Auth Dependencies & Middleware (`app/core/auth.py`)
- `get_current_user`: Trích xuất token từ header `Authorization: Bearer <token>`, giải mã payload và nạp đối tượng `User` từ database. Trả về `401 Unauthorized` nếu thiếu/sai token hoặc user bị vô hiệu hóa.
- `require_admin`: Kế thừa `get_current_user`, kiểm tra `user.role == UserRole.ADMIN`; trả về `403 Forbidden` nếu người dùng không phải Admin.

### 5.4. Segments CRUD & Policy Updates (`app/api/segments.py`)
- `GET /api/segments`: Yêu cầu `get_current_user` (cả `USER` và `ADMIN` đều được xem danh sách).
- `GET /api/segments/{id}`: Yêu cầu `get_current_user` (xem chi tiết 1 đoạn đường).
- `GET /api/segments/{id}/history`: Yêu cầu `get_current_user`.
- `POST /api/segments`: Yêu cầu `require_admin` (chỉ Admin mới có quyền tạo mới, trả về 201).
- `PUT /api/segments/{id}`: Yêu cầu `require_admin` (chỉ Admin mới có quyền sửa). Nhận schema `SegmentUpdate` cho phép cập nhật linh hoạt các trường gửi lên, trả về 200.
- `DELETE /api/segments/{id}`: Yêu cầu `require_admin` (chỉ Admin mới có quyền xóa). Xóa sạch toàn bộ bản ghi `TrafficObservation` có `segment_id == id` trước để tránh lỗi khóa ngoại, sau đó xóa segment, trả về `{"message": "Segment deleted successfully"}`.

### 5.5. Các quyết định kỹ thuật chuẩn hóa (Builder's Calls):
1. **Định dạng Request Login (`/api/auth/login`)**: Hỗ trợ chuẩn JSON payload `{"username": "...", "password": "..."}` cho frontend Vite, đồng thời hỗ trợ cả `application/x-www-form-urlencoded` để nút "Authorize" trên Swagger UI hoạt động tiện lợi.
2. **Quy tắc Đăng ký (`/api/auth/register`)**: Không cho phép client tự truyền role `ADMIN` trong payload đăng ký; mọi tài khoản đăng ký mới luôn mặc định là `USER`. Tài khoản Admin được khởi tạo an toàn qua script seed (`scripts/seed_demo.py`) hoặc script quản trị.
3. **Phạm vi bảo vệ các endpoint khác**: Giữ nguyên `GET /api/traffic/current`, `GET /api/forecast` phục vụ cho giao diện bản đồ public của người dân xem tình trạng tắc đường, và yêu cầu quyền Admin cho việc nạp dữ liệu thủ công / sensor nếu cần.
4. **Semantics của `PUT /api/segments/{id}`**: Hỗ trợ schema `SegmentUpdate` với các trường tuỳ chọn (`Optional`), cho phép Admin cập nhật một phần hoặc toàn bộ thông tin đoạn đường mà không bắt buộc phải gửi lại các trường không thay đổi.

---

## 6. What's Left to the Builder
- Thiết lập secret key mặc định trong `Settings` (ví dụ `JWT_SECRET_KEY: str = "supersecret-jwt-key-for-dev-only"`).
- Định nghĩa schema Pydantic cho User (`UserCreate`, `UserRead`, `UserLogin`, `TokenResponse`).
- Xử lý migration Alembic tự động phát hiện bảng `users`.
