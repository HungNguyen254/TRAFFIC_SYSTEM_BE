# User Avatar Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gộp các trường lưu trữ và xử lý ảnh đại diện (avatar) của User trực tiếp vào model `User` (`app/models/user.py`) và schema `UserResponse`, loại bỏ model tách rời `UserAvatar`, cập nhật các endpoint và schema patch tương thích ngược.

**Architecture:** Avatar được lưu dưới dạng byte blob (`avatar_data`) và MIME type (`avatar_content_type`) trực tiếp trong bảng `users`. Endpoint `/api/v1/auth/me/avatar` thao tác trực tiếp trên bản ghi `User` của người dùng hiện tại, schema `UserResponse` có thêm `has_avatar: bool`, và schema patch tự động thêm cột / di chuyển dữ liệu nếu CSDL đang chạy bảng cũ.

**Tech Stack:** Python 3.14, FastAPI, SQLModel / SQLAlchemy, SQLite / PostgreSQL, pytest.

**Spec:** [docs/superpowers/specs/2026-11-23-user-avatar-consolidation-design.md](file:///home/PageNguyen/Projects/BE/docs/superpowers/specs/2026-11-23-user-avatar-consolidation-design.md)

## Global Constraints

- Các cột avatar trên bảng `users` (`avatar_content_type`, `avatar_data`, `avatar_updated_at`) phải luôn ở trạng thái `nullable=True` với giá trị mặc định là `None`.
- Giữ nguyên hợp đồng API đối với các endpoints `/api/v1/auth/me/avatar` (GET, PUT, DELETE) để Frontend tiếp tục hoạt động mà không bị gãy vỡ.
- Định dạng ảnh hợp lệ: PNG (`image/png`), JPEG (`image/jpeg`), WebP (`image/webp`). Giới hạn dung lượng: tối đa 2 MB (`MAX_AVATAR_BYTES = 2 * 1024 * 1024`).

## Review Focus

1. Người dùng mới đăng ký hoặc chưa từng tải ảnh: gọi `GET /api/v1/auth/me/avatar` phải trả về 404 với thông báo `"Tài khoản chưa có ảnh đại diện."`, `GET /api/v1/auth/me` trả về `has_avatar: false`.
2. Đăng ký tài khoản mới (`POST /api/v1/auth/register`): tạo thành công mà không yêu cầu dữ liệu avatar.
3. Người dùng cập nhật avatar (`PUT /api/v1/auth/me/avatar`): ghi đè ảnh cũ, cập nhật `avatar_content_type`, `avatar_data`, `avatar_updated_at`, và `GET /api/v1/auth/me` ngay sau đó trả về `has_avatar: true`.
4. Người dùng xóa avatar (`DELETE /api/v1/auth/me/avatar`): đặt các trường avatar về `None`, gọi `GET /api/v1/auth/me/avatar` tiếp theo trả về 404.
5. CSDL đã tồn tại (`traffic.db` hoặc PostgreSQL): hệ thống khởi động chạy `init_db()` tự động bổ sung cột vào `users` và chuyển dữ liệu từ `user_avatars` sang `users` nếu bảng cũ còn tồn tại.

---

### Task 1: Cập nhật Model User và Schema Auth

**Files:**
- Modify: `app/models/user.py`
- Modify: `app/schemas/auth.py`
- Modify: `app/models/__init__.py`
- Test: `tests/test_user_avatar_api.py`

**Interfaces:**
- Consumes: Không
- Produces:
  - `User.avatar_content_type: str | None`
  - `User.avatar_data: bytes | None`
  - `User.avatar_updated_at: datetime | None`
  - `UserResponse.has_avatar: bool = False`
  - `AvatarUploadResponse(BaseModel)` với `content_type: str`, `message: str = "Cập nhật ảnh đại diện thành công."`

- [ ] **Step 1: Viết test kiểm tra khởi tạo User và Schema UserResponse**

Trong `tests/test_user_avatar_api.py`:
```python
def test_user_model_avatar_fields_default_to_none():
    user = User(
        email="test-defaults@example.com",
        password_hash="hash",
        full_name="Default User",
        role="user",
    )
    assert user.avatar_content_type is None
    assert user.avatar_data is None
    assert user.avatar_updated_at is None


def test_user_response_schema_has_avatar():
    from app.schemas.auth import UserResponse
    res = UserResponse(
        user_id=uuid.uuid4(),
        email="test@example.com",
        full_name="Test User",
        role="user",
        plan="standard",
        created_at=datetime.now(UTC),
        has_avatar=True,
    )
    assert res.has_avatar is True
```

- [ ] **Step 2: Chạy test để xác nhận fail hoặc import error hiện tại**

Run: `/home/PageNguyen/.local/bin/uv run --with pytest pytest tests/test_user_avatar_api.py -k test_user_model_avatar_fields_default_to_none -v`
Expected: FAIL (do lỗi import `app.models.user_avatar` hoặc thiếu attribute `avatar_content_type`).

- [ ] **Step 3: Cập nhật `app/models/user.py`, `app/schemas/auth.py`, `app/models/__init__.py`**

1. Trong `app/models/user.py`:
   - Xóa `content_type` và `image_data` (cũ, non-nullable).
   - Thêm:
     ```python
     avatar_content_type: str | None = Field(default=None, max_length=32, nullable=True)
     avatar_data: bytes | None = Field(
         default=None,
         sa_column=sa.Column(sa.LargeBinary, nullable=True),
     )
     avatar_updated_at: datetime | None = Field(default=None, nullable=True)
     ```
2. Trong `app/schemas/auth.py`:
   - Thêm class:
     ```python
     class AvatarUploadResponse(BaseModel):
         content_type: str
         message: str = "Cập nhật ảnh đại diện thành công."
     ```
   - Thêm trường `has_avatar: bool = False` vào `UserResponse`.
3. Trong `app/models/__init__.py`:
   - Đảm bảo không còn import `UserAvatar`.

- [ ] **Step 4: Chạy test model để xác nhận pass**

Run: `/home/PageNguyen/.local/bin/uv run --with pytest pytest tests/test_user_avatar_api.py -k test_user_model_avatar_fields_default_to_none -v` (sau khi xử lý tạm import tại auth.py nếu cần)
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/models/user.py app/schemas/auth.py app/models/__init__.py
git commit -m "feat(auth): consolidate avatar fields into User model and UserResponse schema"
```

---

### Task 2: Cập nhật Endpoints `/me/avatar` và `/me` trong Auth Router

**Files:**
- Modify: `app/api/v1/endpoints/auth.py`
- Test: `tests/test_user_avatar_api.py`

**Interfaces:**
- Consumes:
  - `User.avatar_content_type`
  - `User.avatar_data`
  - `User.avatar_updated_at`
  - `AvatarUploadResponse`
- Produces:
  - `GET /me/avatar`: trả về `Response` (image binary) hoặc 404
  - `PUT /me/avatar`: trả về `StandardResponse[AvatarUploadResponse]`
  - `DELETE /me/avatar`: trả về `StandardResponse[None]`
  - `GET /me`: trả về `StandardResponse[UserResponse]` với `has_avatar: bool`

- [ ] **Step 1: Cập nhật các hàm endpoint trong `app/api/v1/endpoints/auth.py`**

1. Xóa `from app.models.user_avatar import UserAvatar`.
2. Import `AvatarUploadResponse` từ `app.schemas.auth`.
3. Sửa `get_me` (và `register`):
   ```python
   user_res = UserResponse(
       user_id=current_user.user_id,
       email=current_user.email,
       full_name=current_user.full_name,
       role=current_user.role,
       plan=current_user.plan,
       created_at=current_user.created_at,
       has_avatar=bool(current_user.avatar_data),
   )
   ```
4. Sửa `get_my_avatar`:
   ```python
   if not current_user.avatar_data or not current_user.avatar_content_type:
       raise HTTPException(
           status_code=status.HTTP_404_NOT_FOUND,
           detail="Tài khoản chưa có ảnh đại diện.",
       )
   return Response(
       content=current_user.avatar_data,
       media_type=current_user.avatar_content_type,
       headers={
           "Cache-Control": "private, no-store",
           "X-Content-Type-Options": "nosniff",
       },
   )
   ```
5. Sửa `upload_my_avatar`:
   - response_model: `StandardResponse[AvatarUploadResponse]`
   - Thay vì query `UserAvatar`, cập nhật trực tiếp `current_user`:
     ```python
     current_user.avatar_content_type = content_type
     current_user.avatar_data = bytes(image_data)
     current_user.avatar_updated_at = datetime.now(UTC)
     session.add(current_user)
     session.commit()
     session.refresh(current_user)

     return success_response(
         request=request,
         message="Cập nhật ảnh đại diện thành công.",
         data=AvatarUploadResponse(content_type=content_type),
     )
     ```
6. Sửa `delete_my_avatar`:
   ```python
   if current_user.avatar_data is not None:
       current_user.avatar_content_type = None
       current_user.avatar_data = None
       current_user.avatar_updated_at = None
       session.add(current_user)
       session.commit()
       session.refresh(current_user)
   return success_response(
       request=request,
       message="Đã xóa ảnh đại diện.",
       data=None,
   )
   ```

- [ ] **Step 2: Cập nhật và bổ sung test cases trong `tests/test_user_avatar_api.py`**

Cập nhật fixture `auth_headers` tạo User mà không cần truyền avatar, kiểm tra luồng:
- Đăng nhập -> `GET /me` trả về `has_avatar == False`
- `GET /me/avatar` -> 404
- `PUT /me/avatar` (PNG hợp lệ) -> 200
- `GET /me` trả về `has_avatar == True`
- `GET /me/avatar` -> 200, đúng Content-Type và binary payload
- `DELETE /me/avatar` -> 200
- `GET /me/avatar` -> 404
- `GET /me` trả về `has_avatar == False`

- [ ] **Step 3: Chạy test suite `test_user_avatar_api.py`**

Run: `/home/PageNguyen/.local/bin/uv run --with pytest pytest tests/test_user_avatar_api.py -v`
Expected: ALL PASS.

- [ ] **Step 4: Commit**

```bash
git add app/api/v1/endpoints/auth.py tests/test_user_avatar_api.py
git commit -m "feat(auth): update avatar endpoints to persist directly on User record"
```

---

### Task 3: Schema Patches & Migration trong `app/core/database.py`

**Files:**
- Modify: `app/core/database.py`
- Test: `tests/test_user_avatar_api.py`

**Interfaces:**
- Consumes: CSDL engine & metadata
- Produces: Cập nhật cột `avatar_content_type`, `avatar_data`, `avatar_updated_at` trên bảng `users` thực tế và migrate dữ liệu từ `user_avatars` nếu có.

- [ ] **Step 1: Viết test cho hàm `_apply_schema_patches` với bảng users cũ**

Trong `tests/test_user_avatar_api.py`:
- Tạo engine SQLite in-memory chỉ có bảng `users` cấu trúc cũ (không có avatar columns) và bảng `user_avatars`.
- Gọi `_apply_schema_patches()`.
- Kiểm tra các cột avatar đã được thêm vào bảng `users` và dữ liệu từ `user_avatars` được copy sang `users`.

- [ ] **Step 2: Cập nhật hàm `_apply_schema_patches()` trong `app/core/database.py`**

Bổ sung kiểm tra và thực thi:
```python
if "avatar_content_type" not in user_cols:
    logger.info("Applying schema patch: adding 'avatar_content_type' to 'users'...")
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN avatar_content_type VARCHAR(32)"))
if "avatar_data" not in user_cols:
    logger.info("Applying schema patch: adding 'avatar_data' to 'users'...")
    with engine.begin() as conn:
        # SQLite uses BLOB, Postgres uses BYTEA or BLOB
        blob_type = "BYTEA" if "postgresql" in str(engine.url) else "BLOB"
        conn.execute(text(f"ALTER TABLE users ADD COLUMN avatar_data {blob_type}"))
if "avatar_updated_at" not in user_cols:
    logger.info("Applying schema patch: adding 'avatar_updated_at' to 'users'...")
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN avatar_updated_at TIMESTAMP"))

# Migrate existing data from user_avatars if table exists
if inspector.has_table("user_avatars"):
    logger.info("Migrating data from 'user_avatars' to 'users'...")
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE users
            SET avatar_content_type = (SELECT content_type FROM user_avatars WHERE user_avatars.user_id = users.user_id),
                avatar_data = (SELECT image_data FROM user_avatars WHERE user_avatars.user_id = users.user_id),
                avatar_updated_at = (SELECT updated_at FROM user_avatars WHERE user_avatars.user_id = users.user_id)
            WHERE user_id IN (SELECT user_id FROM user_avatars)
        """))
```

- [ ] **Step 3: Chạy test migration và chạy patch trên `traffic.db`**

Run: `/home/PageNguyen/.local/bin/uv run --with pytest pytest tests/test_user_avatar_api.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add app/core/database.py
git commit -m "feat(db): add schema patches and migration for avatar fields on users table"
```

---

### Task 4: Chạy toàn bộ Test Suite & Verification

**Files:**
- All tests in `tests/`

- [ ] **Step 1: Chạy toàn bộ test suite dự án**

Run: `/home/PageNguyen/.local/bin/uv run --with pytest pytest -v`
Expected: 100% tests PASS (không còn lỗi ModuleNotFoundError: app.models.user_avatar).

- [ ] **Step 2: Kiểm tra `git status` và `git diff`**

Đảm bảo:
- `app/models/user_avatar.py` đã bị xóa hoàn toàn khỏi git.
- Không còn sót import nào của `UserAvatar` trong toàn bộ codebase.
- Định dạng code sạch sẽ.

- [ ] **Step 3: Commit hoàn thiện**

```bash
git add -A
git commit -m "chore: finalize user avatar consolidation and cleanup"
```
