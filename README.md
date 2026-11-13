# Traffic System BE

Hệ thống API Backend phục vụ giám sát, định tuyến và dự báo tình trạng giao thông thông minh, xây dựng trên nền tảng **FastAPI**, **SQLModel**, **NetworkX** và **Scikit-learn**.

---

## Tính năng nổi bật

- **Dự báo giao thông bằng Machine Learning**: Dự đoán tốc độ trung bình và mức độ ùn tắc giao thông (1-4) theo các mốc thời gian tương lai (30, 60, 120 phút...) bằng mô hình Random Forest.
- **Tìm đường thông minh (Directions & Routing)**: Sử dụng thuật toán Dijkstra trên đồ thị giao thông (NetworkX) để tìm tuyến đường tối ưu:
  - `distance`: Ưu tiên quãng đường ngắn nhất (km).
  - `duration`: Ưu tiên thời gian di chuyển nhanh nhất (phút) dựa trên tình trạng giao thông thực tế/dự báo.
-  **Giám sát trạng thái cung đường (Real-time Edge Status)**:
  - Lọc trạng thái các đoạn đường theo khung nhìn bản đồ (**Bounding Box**: `bbox` hoặc `min_lat`, `min_lng`, `max_lat`, `max_lng`).
  - Lọc theo địa giới hành chính (**Quận/Huyện**: hỗ trợ tìm kiếm tiếng Việt không dấu, không phân biệt hoa thường).
  - Trả về thời điểm dữ liệu được cập nhật (`updated_at`), tốc độ di chuyển và nhãn cảnh báo trực quan.
- **Xác thực & Phân quyền (Auth & RBAC)**:
  - Xác thực an toàn qua **JWT (JSON Web Token)**.
  - Mã hóa mật khẩu với **Argon2** (`pwdlib`).
  - Phân quyền theo vai trò (`user`, `admin`).
- **Tái huấn luyện mô hình (ML Retraining)**: Cho phép quản trị viên kích hoạt tiến trình huấn luyện lại mô hình ngầm (`BackgroundTasks`) khi có dữ liệu mới.
- **Bảo mật & Chuẩn hóa API**:
  - Giới hạn tần suất gọi API (**Rate Limiting**) với `SlowAPI`.
  - Phản hồi chuẩn hóa thông qua envelope `StandardResponse`.
  - CORS tùy biến hỗ trợ tích hợp Frontend (React, Vue, Vite...).

---

## Công nghệ sử dụng

- **Ngôn ngữ**: Python >= 3.14
- **Web Framework**: [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/), Starlette
- **ORM & Database**: [SQLModel](https://sqlmodel.tiangolo.com/), SQLAlchemy 2.0
  - Hỗ trợ SQLite (mặc định môi trường dev) và PostgreSQL / Supabase
- **Trí tuệ nhân tạo (AI/ML)**: [Scikit-learn](https://scikit-learn.org/), NumPy, Joblib
- **Mạng lưới & Đồ thị**: [NetworkX](https://networkx.org/)
- **Bảo mật & Rate Limit**: Pwdlib (Argon2), PyJWT, SlowAPI, Pydantic Settings
- **Quản lý gói & Môi trường**: [uv](https://docs.astral.sh/uv/) / pip

---

## Cấu trúc thư mục

```text
BE/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/        # Các API route (auth, directions, edges, predictions, admin)
│   │       └── router.py         # Tập trung router v1
│   ├── core/
│   │   ├── config.py             # Cấu hình Pydantic BaseSettings (.env)
│   │   ├── database.py           # Kết nối Database và SessionDep
│   │   ├── handlers.py           # Custom Exception handlers
│   │   ├── limiter.py            # Khởi tạo SlowAPI rate limiter
│   │   ├── response.py           # Chuẩn hóa envelope StandardResponse
│   │   └── security.py           # Xử lý JWT, băm mật khẩu Argon2, Dependency kiểm tra role
│   ├── middlewares/              # Middleware (CORS, Request logging, v.v.)
│   ├── models/                   # Database models (User, Node, Edge, Prediction)
│   ├── schemas/                  # Pydantic schemas (Request/Response)
│   ├── services/                 # Business logic (Auth, Traffic, Routing, Prediction)
│   └── main.py                   # Điểm khởi chạy ứng dụng FastAPI
├── data/
│   └── synthetic_traffic_dataset.csv # Dữ liệu giao thông mẫu
├── docs/                         # Tài liệu thiết kế và kế hoạch phát triển
├── scripts/
│   ├── generate_synthetic_traffic.py # Sinh dữ liệu giao thông tổng hợp
│   ├── seed_hanoi_network.py         # Nạp dữ liệu các nút giao và cung đường Hà Nội
│   └── train_prediction_model.py     # Huấn luyện mô hình Random Forest
├── tests/                            # Unit & Integration tests
├── .env.example                      # File mẫu biến môi trường
├── pyproject.toml                    # Cấu hình dự án và dependencies
└── requirements.txt                  # Danh sách dependencies đã ghim phiên bản
```

---

## Hướng dẫn cài đặt và khởi chạy

### 1. Yêu cầu hệ thống
- Python `>= 3.14` (hoặc cài đặt thông qua trình quản lý [uv](https://docs.astral.sh/uv/)).

### 2. Cài đặt môi trường

Sử dụng **uv** (khuyên dùng):
```bash
# Tạo môi trường ảo và cài đặt thư viện
uv sync
```

Hoặc sử dụng **pip / venv** truyền thống:
```bash
python3 -m venv .venv
source .venv/bin/activate  # Trên Linux/macOS
# .venv\Scripts\activate   # Trên Windows

pip install -r requirements.txt
```

### 3. Cấu hình biến môi trường
Tạo file `.env` từ file mẫu `.env.example`:
```bash
cp .env.example .env
```
Chỉnh sửa các tham số trong `.env` nếu cần (Database URL, JWT Secret Key, Allowed Origins...).

### 4. Khởi tạo dữ liệu và mô hình AI
Trước khi khởi chạy lần đầu, thực hiện nạp dữ liệu mạng lưới nút giao Hà Nội và huấn luyện mô hình dự báo:

```bash
# Nạp mạng lưới giao thông mẫu Hà Nội vào Database
uv run python scripts/seed_hanoi_network.py

# Huấn luyện mô hình dự báo giao thông (lưu vào app/core/model.joblib)
uv run python scripts/train_prediction_model.py
```

### 5. Khởi chạy máy chủ API
```bash
# Sử dụng uv
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Hoặc kích hoạt venv và chạy trực tiếp
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Hệ thống sẽ chạy tại địa chỉ: `http://127.0.0.1:8000`.

---

## Tài liệu API (Interactive Docs)

Sau khi khởi chạy ứng dụng, bạn có thể truy cập tài liệu API trực quan tại:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### Bảng tóm tắt các Endpoints chính:

| Nhóm | Phương thức | Đường dẫn | Mô tả |
| :--- | :--- | :--- | :--- |
| **Hệ thống** | `GET` | `/api/health` | Kiểm tra trạng thái máy chủ và kết nối cơ sở dữ liệu |
| **Xác thực** | `POST` | `/api/v1/auth/register` | Đăng ký tài khoản người dùng / admin |
| | `POST` | `/api/v1/auth/login` | Đăng nhập nhận Access Token (JWT) |
| | `GET` | `/api/v1/auth/me` | Lấy thông tin tài khoản hiện tại |
| | `POST` | `/api/v1/auth/change-password` | Đổi mật khẩu |
| **Giám sát đường** | `GET` | `/api/v1/edges/status` | Tình trạng giao thông mới nhất (hỗ trợ lọc theo `bbox` hoặc `district`) |
| | `GET` | `/api/v1/edges` | Danh sách nodes & edges kèm mức độ giao thông |
| **Tìm đường** | `GET` | `/api/v1/directions` | Tìm lộ trình tối ưu (`distance` hoặc `duration`) |
| **Dự báo AI** | `POST` | `/api/v1/predictions/forecast` | Dự báo tình trạng tắc đường theo mốc thời gian tương lai |
| **Quản trị** | `POST` | `/api/v1/admin/retrain-model` | Kích hoạt huấn luyện lại mô hình trong background (Yêu cầu quyền Admin) |

---

## Kiểm thử (Testing)

Dự án sử dụng **pytest** để kiểm thử tự động các module schemas, services và API endpoints:

```bash
uv run --with pytest pytest
```
