# Thiết kế: Tích hợp Avatar trực tiếp vào Model và Schema của User

## 1. Mục đích (Intent & Why)
- Hợp nhất việc lưu trữ và quản lý ảnh đại diện (avatar) trực tiếp vào model `User` (`users` table) và schema `UserResponse` thay vì duy trì một bảng/model độc lập `UserAvatar`.
- Giảm số lượng join/query bổ sung, làm gọn cấu trúc cơ sở dữ liệu và đồng nhất cấu trúc dữ liệu người dùng.

## 2. Mục tiêu (Goals, Non-Goals, Anti-Goals)
- **Goals:**
  - Thêm các trường avatar (`avatar_content_type`, `avatar_data`, `avatar_updated_at`) vào model `User` (`app/models/user.py`) dạng nullable.
  - Xóa bỏ triệt để model `UserAvatar` (`app/models/user_avatar.py`) và các import liên quan trong `app/models/__init__.py`.
  - Cập nhật schema `UserResponse` (`app/schemas/auth.py`) thêm trường `has_avatar: bool = False`.
  - Bổ sung schema `AvatarUploadResponse` chuẩn hóa cho API upload avatar.
  - Cập nhật các endpoint `/api/v1/auth/me/avatar` (GET, PUT, DELETE) và `/api/v1/auth/me` để thao tác trực tiếp trên `current_user`.
  - Bổ sung schema migration/patch trong `app/core/database.py` để tương thích CSDL hiện có (`traffic.db`), tự động migrate dữ liệu từ bảng cũ nếu có.
  - Đảm bảo 100% test suite trong `tests/` chạy thành công.
- **Non-Goals:**
  - Không thay đổi endpoint path `/api/v1/auth/me/avatar` (để tránh ảnh hưởng tới FE).
  - Không lưu file avatar lên storage bên ngoài (S3/Cloudinary) trong phạm vi này (vẫn lưu byte blob trong DB).
- **Anti-Goals:**
  - Không để các cột avatar là `nullable=False` gây lỗi khi tạo hoặc đăng ký user mới.
  - Không làm gián đoạn API của Frontend.

## 3. Ràng buộc (Constraints)
- Phải tương thích với database SQLite cục bộ và PostgreSQL trên production.
- Định dạng ảnh hỗ trợ: PNG, JPEG, WebP. Giới hạn kích thước tối đa 2MB.

## 4. Các hướng tiếp cận (Approaches)
- **Phương án 1 (Được chọn):** Đặt tên rõ ràng `avatar_content_type`, `avatar_data`, `avatar_updated_at` (nullable) trong `User`. Thêm `has_avatar` vào `UserResponse` và tạo schema `AvatarUploadResponse`.
  - *Lý do chọn:* Tên trường rõ ràng, không gây xung đột ngữ cảnh với các trường dữ liệu khác của `User`, chuẩn hóa schema phản hồi.
- **Phương án 2 (Loại):** Giữ nguyên tên cột `content_type`, `image_data` trên bảng `users`.
  - *Lý do loại:* Thiếu tiền tố `avatar_` dẫn đến mơ hồ khi đọc schema và khó mở rộng trong tương lai.

## 5. Chi tiết kỹ thuật (Decisions & Details)
1. **Model `User` (`app/models/user.py`):**
   - `avatar_content_type: str | None = Field(default=None, max_length=32, nullable=True)`
   - `avatar_data: bytes | None = Field(default=None, sa_column=sa.Column(sa.LargeBinary, nullable=True))`
   - `avatar_updated_at: datetime | None = Field(default=None, nullable=True)`
2. **Schema (`app/schemas/auth.py`):**
   - `AvatarUploadResponse`: `content_type: str`, `message: str = "Cập nhật ảnh đại diện thành công."`
   - `UserResponse`: thêm `has_avatar: bool = False`.
3. **Endpoint (`app/api/v1/endpoints/auth.py`):**
   - `GET /me/avatar`: kiểm tra `current_user.avatar_data`, trả về binary response; nếu không có thì trả về 404.
   - `PUT /me/avatar`: cập nhật `current_user.avatar_content_type`, `current_user.avatar_data`, `current_user.avatar_updated_at`.
   - `DELETE /me/avatar`: gán cả 3 trường về `None`.
   - `GET /me`: gán `has_avatar=bool(current_user.avatar_data)`.
4. **Database Migration (`app/core/database.py`):**
   - Thêm cột vào bảng `users` nếu chưa có.
   - Di chuyển dữ liệu từ bảng `user_avatars` sang `users` nếu bảng cũ tồn tại.
5. **Tests (`tests/test_user_avatar_api.py`):**
   - Cập nhật test fixtures và các test cases theo logic mới.
