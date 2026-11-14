# 🚦 Traffic System Backend (BE)

Hệ thống API Backend thông minh phục vụ **giám sát thời gian thực**, **định tuyến tìm đường tối ưu** và **dự báo tình trạng ùn tắc giao thông tương lai**. Được xây dựng trên nền tảng **FastAPI**, **SQLModel / SQLAlchemy**, **NetworkX** và **Scikit-learn**.

---

## 📑 Mục lục
- [1. Tổng quan kiến trúc hệ thống](#1-tổng-quan-kiến-trúc-hệ-thống)
- [2. Sơ đồ cơ sở dữ liệu (Database Schema & ERD)](#2-sơ-đồ-cơ-sở-dữ-liệu-database-schema--erd)
- [3. Hướng dẫn cài đặt & Khởi chạy](#3-hướng-dẫn-cài-đặt--khởi-chạy)
- [4. Cấu trúc thư mục dự án](#4-cấu-trúc-thư-mục-dự-án)
- [5. Chuẩn hóa API & Envelope Response](#5-chuẩn-hóa-api--envelope-response)
- [6. Danh mục API chi tiết (Endpoints Reference)](#6-danh-mục-api-chi-tiết-endpoints-reference)
  - [Hệ thống & Health Check](#hệ-thống--health-check)
  - [Xác thực & Phân quyền (Auth & RBAC)](#xác-thực--phân-quyền-auth--rbac)
  - [Giám sát & Quản lý cung đường (Edges & Traffic Status)](#giám-sát--quản-lý-cung-đường-edges--traffic-status)
  - [Tìm đường thông minh (Directions & Routing)](#tìm-đường-thông-minh-directions--routing)
  - [Dự báo giao thông AI (Predictions & Forecast)](#dự-báo-giao-thông-ai-predictions--forecast)
  - [Quản trị viên (Admin Tasks)](#quản-trị-viên-admin-tasks)
- [7. Luồng nghiệp vụ & Cơ chế xử lý chi tiết (Business Flows)](#7-luồng-nghiệp-vụ--cơ-chế-xử-lý-chi-tiết-business-flows)
  - [Luồng 1: Xác thực JWT & Thu hồi Token tức thì](#luồng-1-xác-thực-jwt--thu-hồi-token-tức-thì-token-revocation)
  - [Luồng 2: Giám sát trạng thái đường (Bounding Box & District Filter)](#luồng-2-giám-sát-trạng-thái-đường-bounding-box--district-filter)
  - [Luồng 3: Tìm đường tối ưu (Dijkstra trên NetworkX & Graph Cache)](#luồng-3-tìm-đường-tối-ưu-dijkstra-trên-networkx--graph-cache)
  - [Luồng 4: Dự báo giao thông AI & Heuristic Fallback](#luồng-4-dự-báo-giao-thông-ai--heuristic-fallback)
  - [Luồng 5: Huấn luyện lại mô hình trong tiến trình ngầm (Background Task)](#luồng-5-huấn-luyện-lại-mô-hình-trong-tiến-trình-ngầm-background-task)
- [8. Bảo mật & Giới hạn tần suất (Rate Limiting)](#8-bảo-mật--giới-hạn-tần-suất-rate-limiting)
- [9. Các Scripts tiện ích (CLI Utilities)](#9-các-scripts-tiện-ích-cli-utilities)
- [10. Kiểm thử tự động (Testing)](#10-kiểm-thử-tự-động-testing)

---

## 1. Tổng quan kiến trúc hệ thống

Hệ thống được thiết kế theo mô hình phân lớp hiện đại (**Layered Architecture**), tách biệt rõ ràng giữa Controller/Endpoints, Service Layer, Core Components và Data Layer:

```mermaid
flowchart TD
    Client["Client (Frontend / Mobile / Postman)"] --> RateLimiter["SlowAPI Rate Limiter"]
    RateLimiter --> CORSMiddleware["CORS Middleware"]
    CORSMiddleware --> ExceptionHandler["Global Exception Handlers"]
    
    subgraph APILayer ["API Layer (FastAPI Routers)"]
        R_Auth["/api/v1/auth"]
        R_Edges["/api/v1/edges"]
        R_Directions["/api/v1/directions"]
        R_Predictions["/api/v1/predictions"]
        R_Admin["/api/v1/admin"]
        R_System["/api/health & /api/data"]
    end
    ExceptionHandler --> APILayer

    subgraph ServiceLayer ["Service Layer (Business Logic)"]
        S_Auth["AuthService\n(Argon2, JWT, Token Versioning)"]
        S_Traffic["TrafficService\n(Traffic DB Cache, BBox, District Matcher)"]
        S_Routing["RoutingService\n(NetworkX Graph, Dijkstra Routing)"]
        S_Predict["PredictionService\n(RandomForest, Timeline, Fallback)"]
    end
    
    R_Auth --> S_Auth
    R_Edges --> S_Traffic
    R_Directions --> S_Routing
    R_Predictions --> S_Predict
    R_Admin --> S_Predict
    R_Admin --> S_Traffic

    subgraph DataAndAILayer ["Storage & In-Memory Engines"]
        DB[("Database\n(PostgreSQL Supabase / SQLite)")]
        TrafficCache[("In-Memory Traffic Cache\n(Thread-Safe Lock)")]
        GraphCache[("In-Memory Graph Cache\n(TTL 300s)")]
        MLMemory[("In-Memory ML Model\n(joblib deserialized)")]
    end

    S_Auth <--> DB
    S_Traffic <--> DB
    S_Traffic <--> TrafficCache
    S_Routing <--> DB
    S_Routing <--> GraphCache
    S_Predict <--> DB
    S_Predict <--> MLMemory
```

---

## 2. Sơ đồ cơ sở dữ liệu (Database Schema & ERD)

Hệ thống sử dụng **SQLModel** (xây dựng trên SQLAlchemy 2.0). Dữ liệu hỗ trợ cả **SQLite** (cho môi trường kiểm thử/dev) và **PostgreSQL / Supabase** (môi trường production).

### 2.1. Sơ đồ thực thể quan hệ (ERD)

```mermaid
erDiagram
    NODES ||--o{ EDGES : "from_node (CASCADE)"
    NODES ||--o{ EDGES : "to_node (CASCADE)"
    EDGES ||--o{ PREDICTIONS : "edge_id (CASCADE)"

    USERS {
        uuid user_id PK "UUIDv4 khóa chính"
        string email UK "Email độc nhất, max 100"
        string password_hash "Mật khẩu băm Argon2"
        string full_name "Họ và tên người dùng"
        string role "Vai trò: user / admin"
        int token_version "Phiên bản token kiểm soát thu hồi"
        datetime created_at "Thời điểm tạo tài khoản (UTC)"
    }

    NODES {
        uuid node_id PK "UUIDv4 khóa chính"
        string node_code UK "Mã nút giao (vd: NODE_NTS)"
        string node_name "Tên nút giao (vd: Ngã tư Sở)"
        string district "Quận/Huyện (vd: Đống Đa)"
        float latitude "Tọa độ vĩ độ"
        float longitude "Tọa độ kinh độ"
        string geom "Dữ liệu hình học WKT (tùy chọn)"
        datetime created_at "Thời điểm tạo nút (UTC)"
    }

    EDGES {
        uuid edge_id PK "UUIDv4 khóa chính"
        string edge_code UK "Mã cung đường (vd: EDGE_LANG_01)"
        string street_name "Tên đường phố (vd: Đường Láng)"
        uuid from_node_id FK "FK tham chiếu NODES.node_id"
        uuid to_node_id FK "FK tham chiếu NODES.node_id"
        float length_km "Chiều dài đoạn đường (km)"
        int max_speed_limit "Tốc độ giới hạn tối đa (km/h)"
        string geom "Dữ liệu hình học WKT (tùy chọn)"
        datetime created_at "Thời điểm tạo đoạn đường (UTC)"
    }

    TRAFFIC_DATA {
        uuid id PK "UUIDv4 khóa chính"
        string edge_code "Mã đoạn đường (được đánh chỉ mục)"
        string street_name "Tên đường phố"
        float length_km "Chiều dài (km)"
        int max_speed_limit "Tốc độ giới hạn (km/h)"
        int hour_of_day "Khung giờ (0-23)"
        int day_of_week "Ngày trong tuần (0-6)"
        int is_weekend "Cờ cuối tuần (0 hoặc 1)"
        int is_rush_hour "Cờ giờ cao điểm (0 hoặc 1)"
        float weather_code "Mã thời tiết (0.0=Nắng, 1.0=Mưa, 2.0=Mưa lớn)"
        float average_speed "Vận tốc di chuyển trung bình (km/h)"
        int congestion_level "Mức độ ùn tắc (1: Thoáng -> 4: Kẹt)"
        float risk_factor "Hệ số rủi ro ùn tắc (0.0 -> 1.0)"
        datetime created_at "Thời điểm ghi nhận (UTC)"
    }

    ML_MODELS {
        uuid model_id PK "UUIDv4 khóa chính"
        string model_name "Tên mô hình (vd: traffic_speed_rf)"
        int version "Phiên bản mô hình (1, 2, 3...)"
        bytes model_bytes "Trọng số nhị phân mô hình (LargeBinary BLOB)"
        json metrics "Chỉ số đánh giá (R2 score, sample count...)"
        boolean is_active "Trạng thái đang hoạt động (True/False)"
        datetime created_at "Thời điểm huấn luyện (UTC)"
    }

    PREDICTIONS {
        uuid prediction_id PK "UUIDv4 khóa chính"
        uuid edge_id FK "FK tham chiếu EDGES.edge_id"
        int hour_of_day "Khung giờ dự báo (0-23)"
        float predicted_speed "Tốc độ dự báo (km/h)"
        float risk_factor "Hệ số rủi ro (0.0 -> 1.0)"
        datetime updated_at "Thời điểm cập nhật dự báo (UTC)"
    }
```

### 2.2. Điểm kiến trúc cốt lõi của Database

1. **Quản lý mô hình ML trong Database (`ml_models`)**: Thay vì phụ thuộc vào file tĩnh trên đĩa (`.joblib`), các mô hình sau khi huấn luyện được lưu dưới dạng nhị phân (`LargeBinary`). Hệ thống truy vấn phiên bản có `is_active=True` và `version` cao nhất để nạp vào bộ nhớ.
2. **Loại bỏ phụ thuộc file CSV tĩnh (`traffic_data`)**: Mọi dữ liệu lịch sử giao thông phục vụ huấn luyện AI và tính toán trạng thái giao thông đều được quản lý tập trung trong bảng `traffic_data`.
3. **Cơ chế thu hồi Token tức thời (`token_version` trong `users`)**: Cho phép thu hồi token ngay lập tức khi đổi mật khẩu mà không cần lưu blacklist Redis phức tạp.

---

## 3. Hướng dẫn cài đặt & Khởi chạy

### 3.1. Yêu cầu hệ thống
- **Python**: Phiên bản `>= 3.14`
- **Trình quản lý gói**: Khuyến nghị dùng [uv](https://docs.astral.sh/uv/) (hoặc `pip` / `venv` chuẩn)
- **Hệ điều hành**: Linux, macOS hoặc Windows

### 3.2. Cài đặt môi trường

Sử dụng **uv** (nhanh và chuẩn xác nhất):
```bash
# Clone repository
git clone <repository_url>
cd BE

# Đồng bộ môi trường ảo và cài đặt toàn bộ dependencies
uv sync
```

Hoặc sử dụng **pip / venv** truyền thống:
```bash
python3 -m venv .venv
source .venv/bin/activate       # Trên Linux/macOS
# .venv\Scripts\activate        # Trên Windows

pip install -r requirements.txt
```

### 3.3. Cấu hình biến môi trường (`.env`)

Sao chép file mẫu `.env.example` thành `.env`:
```bash
cp .env.example .env
```

Các tham số quan trọng trong `.env`:
```ini
APP_NAME="Traffic System BE"
ENVIRONMENT="dev"
DEBUG=True
HOST="127.0.0.1"
PORT=8000

# Danh sách domain Frontend được phép gọi CORS
ALLOWED_ORIGINS=["http://127.0.0.1:5173", "http://localhost:5173"]

# URL Database:
# Mặc định SQLite (Local Dev):
DATABASE_URL="sqlite:///./traffic.db"
# Supabase PostgreSQL (Production):
# DATABASE_URL="postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres"

# Bảo mật JWT (Production bắt buộc thay đổi khóa bí mật >= 32 ký tự)
JWT_SECRET_KEY="dev-secret-key-change-in-production-must-be-long-enough"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE=1440

# Giới hạn tần suất gọi API
RATE_LIMIT_ENABLED=True
RATE_LIMIT_DEFAULT="60/minute"
```

### 3.4. Khởi tạo dữ liệu và nạp mô hình AI

Chạy tuần tự các lệnh sau trước lần chạy máy chủ đầu tiên:

```bash
# 1. Khởi tạo và nạp mạng lưới nút giao & cung đường Hà Nội
uv run python scripts/seed_hanoi_network.py

# 2. Nhập dữ liệu giao thông mẫu từ CSV vào bảng database `traffic_data`
uv run python scripts/import_traffic_csv_to_db.py --truncate

# 3. Huấn luyện mô hình Machine Learning và lưu nhị phân vào bảng `ml_models`
uv run python scripts/train_prediction_model.py
```

### 3.5. Khởi chạy máy chủ API

```bash
# Chạy máy chủ phát triển với chế độ tự động reload
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Truy cập kiểm tra:
- **API Root**: [http://127.0.0.1:8000/api/data](http://127.0.0.1:8000/api/data)
- **Health Check**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- **Tài liệu Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Tài liệu ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 4. Cấu trúc thư mục dự án

```text
BE/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── admin.py          # API quản trị (Huấn luyện lại mô hình ML ngầm)
│   │       │   ├── auth.py           # API xác thực (Đăng ký, Đăng nhập, Profile, Đổi mật khẩu)
│   │       │   ├── directions.py     # API tìm đường tối ưu (Dijkstra)
│   │       │   ├── edges.py          # API trạng thái đường & CRUD Edges
│   │       │   └── predictions.py    # API dự báo tình trạng giao thông tương lai
│   │       └── router.py             # Tổng hợp các endpoint v1
│   ├── core/
│   │   ├── config.py                 # Cấu hình Pydantic BaseSettings & validate môi trường
│   │   ├── database.py               # Kết nối cơ sở dữ liệu, SessionDep, health probe
│   │   ├── exceptions.py             # Định nghĩa mã lỗi tùy chỉnh (AppException)
│   │   ├── handlers.py               # Xử lý ngoại lệ tập trung (Centralized Exception Handlers)
│   │   ├── limiter.py                # Cấu hình Rate Limiter (SlowAPI)
│   │   ├── response.py               # Cấu trúc envelope StandardResponse chuẩn hóa
│   │   └── security.py               # Băm mật khẩu Argon2, tạo/giải mã JWT, RBAC dependencies
│   ├── middlewares/
│   │   └── middleware.py             # Cấu hình CORS middleware
│   ├── models/                       # Các thực thể dữ liệu SQLModel (Database Tables)
│   │   ├── edge.py                   # Cung đường nối 2 nút giao
│   │   ├── ml_model.py               # Bản ghi nhị phân mô hình ML
│   │   ├── node.py                   # Nút giao thông
│   │   ├── prediction.py             # Dữ liệu dự báo theo giờ
│   │   ├── traffic_data.py           # Bản ghi dữ liệu giao thông lịch sử
│   │   └── user.py                   # Tài khoản người dùng & phân quyền
│   ├── schemas/                      # Pydantic Schemas (Request Payload & Response DTO)
│   │   ├── auth.py
│   │   ├── edge_status.py
│   │   ├── prediction.py
│   │   ├── routing.py
│   │   └── traffic.py
│   ├── services/                     # Lớp xử lý nghiệp vụ chính (Business Logic Layer)
│   │   ├── auth_service.py           # Nghiệp vụ đăng ký, xác thực, đổi mật khẩu
│   │   ├── prediction_service.py     # Nạp mô hình ML từ DB, dự báo timeline, fallback
│   │   ├── routing_service.py        # Dựng đồ thị NetworkX, chạy thuật toán Dijkstra
│   │   └── traffic_service.py        # Tính toán snapshot tốc độ, lọc BBox / District
│   └── main.py                       # Điểm khởi chạy FastAPI, Lifespan kết nối DB & nạp model
├── data/
│   └── synthetic_traffic_dataset.csv # File dữ liệu giao thông mẫu dự phòng
├── scripts/
│   ├── generate_synthetic_traffic.py # Sinh dữ liệu giao thông giả lập
│   ├── import_traffic_csv_to_db.py   # Nhập dữ liệu CSV vào bảng traffic_data
│   ├── seed_hanoi_network.py         # Nạp các nút giao và cung đường mẫu Hà Nội
│   └── train_prediction_model.py     # Huấn luyện Random Forest & lưu vào bảng ml_models
├── tests/                            # Bộ kiểm thử tự động toàn diện (30 unit & integration tests)
├── .env.example                      # File mẫu biến môi trường
├── pyproject.toml                    # Quản lý cấu hình dự án và dependencies
└── requirements.txt                  # Danh sách dependencies đã ghim phiên bản
```

---

## 5. Chuẩn hóa API & Envelope Response

Toàn bộ các phản hồi từ API (cả thành công lẫn thất bại) đều được bọc trong một chuẩn phong bì duy nhất: **`StandardResponse[T]`**.

### 5.1. Định dạng phản hồi thành công (`HTTP 200 OK`)
```json
{
  "status_code": 200,
  "message": "Thông điệp mô tả kết quả xử lý thành công",
  "data": { ... },
  "error": null,
  "path": "/api/v1/auth/me",
  "timestamp": "2026-11-14T10:30:00.000000Z"
}
```

### 5.2. Định dạng phản hồi khi có lỗi (`HTTP 4xx / 5xx`)
```json
{
  "status_code": 401,
  "message": "Token không hợp lệ hoặc đã bị vô hiệu hóa.",
  "data": null,
  "error": "UNAUTHORIZED",
  "path": "/api/v1/auth/me",
  "timestamp": "2026-11-14T10:30:00.000000Z"
}
```

---

## 6. Danh mục API chi tiết (Endpoints Reference)

### Bảng tóm tắt các Endpoints

| Nhóm | Phương thức | Đường dẫn | Quyền hạn | Giới hạn (Rate Limit) | Mục đích chính |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **System** | `GET` | `/api/data` | Public | - | Lời chào mừng và xác nhận API hoạt động |
| | `GET` | `/api/health` | Public | - | Kiểm tra sức khỏe máy chủ & trạng thái DB |
| **Auth** | `POST` | `/api/v1/auth/register` | Public | 5 req/phút | Đăng ký tài khoản người dùng mới |
| | `POST` | `/api/v1/auth/login` | Public | 5 req/phút | Đăng nhập nhận Access Token (JWT) |
| | `GET` | `/api/v1/auth/me` | Bearer Token | - | Lấy thông tin tài khoản hiện tại |
| | `POST` | `/api/v1/auth/change-password` | Bearer Token | 5 req/phút | Đổi mật khẩu & vô hiệu hóa token cũ |
| **Edges** | `GET` | `/api/v1/edges/status` | Public | 60 req/phút | Lấy tình trạng tắc đường theo BBox / Quận |
| | `GET` | `/api/v1/edges` | Public | 30 req/phút | Lấy danh sách nodes & edges kèm mức tắc |
| | `GET` | `/api/v1/edges/{edge_id}` | Public | - | Lấy chi tiết thông tin một đoạn đường |
| | `POST` | `/api/v1/edges` | **Admin** | - | Tạo mới một đoạn đường |
| | `PUT` | `/api/v1/edges/{edge_id}` | **Admin** | - | Cập nhật thông tin đoạn đường |
| | `DELETE`| `/api/v1/edges/{edge_id}` | **Admin** | - | Xóa đoạn đường khỏi hệ thống |
| **Routing**| `GET` | `/api/v1/directions` | Public | 20 req/phút | Tìm đường tối ưu (`distance` hoặc `duration`) |
| **Predict**| `POST` | `/api/v1/predictions/forecast`| Public | 10 req/phút | Dự báo dòng thời gian tắc đường tương lai |
| **Admin** | `POST` | `/api/v1/admin/retrain-model` | **Admin** | 2 req/phút | Kích hoạt huấn luyện lại mô hình AI ngầm |

---

### Chi tiết các API

#### Hệ thống & Health Check

##### 1. `GET /api/health`
- **Mục đích**: Kiểm tra tình trạng hoạt động của máy chủ và kết nối đến cơ sở dữ liệu (PostgreSQL/SQLite).
- **Ví dụ gọi cURL**:
```bash
curl -X GET "http://127.0.0.1:8000/api/health"
```
- **Dữ liệu trả về**:
```json
{
  "status_code": 200,
  "message": "Health check passed",
  "data": {
    "status": "ok",
    "database": "connected"
  },
  "error": null,
  "path": "/api/health",
  "timestamp": "2026-11-14T10:30:00Z"
}
```

---

#### Xác thực & Phân quyền (Auth & RBAC)

##### 1. `POST /api/v1/auth/register`
- **Mục đích**: Đăng ký người dùng mới. Mật khẩu được mã hóa an toàn bằng thuật toán **Argon2**.
- **Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "Nguyễn Văn A"
}
```

##### 2. `POST /api/v1/auth/login`
- **Mục đích**: Xác thực người dùng và cấp JWT Access Token.
- **Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```
- **Dữ liệu trả về**:
```json
{
  "status_code": 200,
  "message": "Đăng nhập thành công",
  "data": {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "role": "user",
    "user_id": "8bb38584-6330-4e3d-bb62-421711e7fc92"
  }
}
```

##### 3. `GET /api/v1/auth/me`
- **Mục đích**: Lấy thông tin tài khoản đang đăng nhập.
- **Header bắt buộc**: `Authorization: Bearer <access_token>`

##### 4. `POST /api/v1/auth/change-password`
- **Mục đích**: Đổi mật khẩu người dùng. Hệ thống sẽ tăng `token_version` trong database, giúp **lập tức vô hiệu hóa mọi access token cũ**.
- **Request Body**:
```json
{
  "current_password": "SecurePassword123!",
  "new_password": "NewUltraSecurePass456!"
}
```

---

#### Giám sát & Quản lý cung đường (Edges & Traffic Status)

##### 1. `GET /api/v1/edges/status`
- **Mục đích**: Trả về tình trạng giao thông mới nhất của các đoạn đường.
- **Các tham số lọc (Query Params)**:
  - `bbox`: Chuỗi khung nhìn bản đồ, định dạng `"min_lng,min_lat,max_lng,max_lat"` (chuẩn GeoJSON/Mapbox) hoặc `"min_lat,min_lng,max_lat,max_lng"`.
  - Hoặc 4 tham số tọa độ độc lập: `min_lat`, `min_lng`, `max_lat`, `max_lng`.
  - `district` / `area`: Lọc theo Quận/Huyện (vd: `Đống Đa`, `Cau Giay` — **hỗ trợ tìm kiếm tiếng Việt không dấu, không phân biệt hoa thường**).
  - `hour`: Khung giờ (0-23, mặc định là giờ hiện tại theo múi giờ Hà Nội `Asia/Ho_Chi_Minh`).
  - `day_of_week`: Thứ trong tuần (0: Thứ 2 ... 6: Chủ Nhật, mặc định là ngày hiện tại).
- **Ví dụ gọi cURL**:
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/edges/status?district=Dong%20Da&hour=18"
```
- **Cấu trúc dữ liệu trả về**:
```json
{
  "status_code": 200,
  "message": "Lấy tình trạng của 24 đoạn đường thành công",
  "data": {
    "total": 24,
    "updated_at": "2026-11-14T10:30:00Z",
    "filters": {
      "district": "Dong Da",
      "hour": 18,
      "day_of_week": 5
    },
    "edges": [
      {
        "edge_id": "7ac18c89-c439-4d64-8898-75b8e97f0eb9",
        "edge_code": "EDGE_LANG_01",
        "street_name": "Đường Láng",
        "length_km": 1.2,
        "max_speed_limit": 50,
        "from_node": {
          "node_code": "NODE_NTS",
          "node_name": "Ngã tư Sở",
          "district": "Đống Đa",
          "lat": 21.0025,
          "lng": 105.8198
        },
        "to_node": {
          "node_code": "NODE_CG",
          "node_name": "Nút giao Cầu Giấy",
          "district": "Cầu Giấy",
          "lat": 21.0332,
          "lng": 105.7985
        },
        "speed": 16.5,
        "congestion_level": 3,
        "congestion_text": "Ùn tắc nghiêm trọng",
        "updated_at": "2026-11-14T10:30:00Z"
      }
    ]
  }
}
```

##### 2. `GET /api/v1/edges`
- **Mục đích**: Trả về dữ liệu kết hợp cả danh sách `nodes` và `edges` kèm thông số giao thông phục vụ hiển thị lớp phủ bản đồ (Map overlay).

##### 3. Quản lý Cung đường (CRUD Edges - Yêu cầu quyền Admin)
- `POST /api/v1/edges`: Tạo đoạn đường mới.
- `GET /api/v1/edges/{edge_id}`: Xem chi tiết đoạn đường.
- `PUT /api/v1/edges/{edge_id}`: Cập nhật thông tin đoạn đường.
- `DELETE /api/v1/edges/{edge_id}`: Xóa đoạn đường.

---

#### Tìm đường thông minh (Directions & Routing)

##### `GET /api/v1/directions`
- **Mục đích**: Tìm lộ trình tối ưu giữa hai nút giao bằng thuật toán Dijkstra trên đồ thị đa hướng có hướng (`nx.MultiDiGraph`).
- **Query Params**:
  - `origin_node_id` (UUID): ID của nút giao xuất phát.
  - `destination_node_id` (UUID): ID của nút giao đích.
  - `weight_mode`: Chế độ tối ưu hóa:
    - `"distance"`: Ưu tiên **quãng đường ngắn nhất** (tổng km nhỏ nhất).
    - `"duration"`: Ưu tiên **thời gian di chuyển nhanh nhất** (tổng phút nhỏ nhất, tính theo vận tốc cho phép và tình trạng giao thông).
- **Ví dụ gọi cURL**:
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/directions?origin_node_id=11111111-1111-1111-1111-111111111111&destination_node_id=22222222-2222-2222-2222-222222222222&weight_mode=duration"
```
- **Dữ liệu trả về**:
```json
{
  "status_code": 200,
  "message": "Tìm tuyến thành công",
  "data": {
    "origin_node_id": "11111111-1111-1111-1111-111111111111",
    "destination_node_id": "22222222-2222-2222-2222-222222222222",
    "node_ids": ["11111111-...", "22222222-..."],
    "node_names": ["Ngã tư Sở", "Nút giao Cầu Giấy"],
    "edge_ids": ["7ac18c89-..."],
    "steps": [
      {
        "edge_id": "7ac18c89-...",
        "edge_code": "EDGE_LANG_01",
        "street_name": "Đường Láng",
        "length_km": 1.2,
        "travel_min": 2.4,
        "speed_kmh": 30.0
      }
    ],
    "polyline": [
      [105.8198, 21.0025],
      [105.7985, 21.0332]
    ],
    "total_distance_km": 1.2,
    "total_duration_min": 2.4
  }
}
```

---

#### Dự báo giao thông AI (Predictions & Forecast)

##### `POST /api/v1/predictions/forecast`
- **Mục đích**: Dự đoán tốc độ di chuyển, chỉ số rủi ro và mức độ tắc nghẽn theo dòng thời gian tương lai (ví dụ sau 30 phút, 60 phút, 120 phút...) bằng mô hình **Random Forest Regressor**.
- **Request Body**:
```json
{
  "edge_id": "7ac18c89-c439-4d64-8898-75b8e97f0eb9",
  "base_time": "2026-11-14T17:00:00Z",
  "minutes_ahead": [30, 60, 120],
  "weather": "rain"
}
```
*(Ghi chú: Có thể truyền `street_name` thay vì `edge_id` nếu người dùng tìm kiếm theo tên đường).*

- **Dữ liệu trả về**:
```json
{
  "status_code": 200,
  "message": "Dự báo tình trạng giao thông thành công",
  "data": {
    "edge_id": "7ac18c89-c439-4d64-8898-75b8e97f0eb9",
    "street_name": "Đường Láng",
    "max_speed_limit": 50,
    "base_time": "2026-11-14T17:00:00Z",
    "weather": "rain",
    "timeline": [
      {
        "minutes_ahead": 30,
        "target_time": "2026-11-14T17:30:00Z",
        "hour_of_day": 17,
        "day_of_week": 5,
        "predicted_speed": 16.8,
        "max_speed_limit": 50,
        "risk_factor": 0.66,
        "congestion_level": 3,
        "description": "Đông đúc, nguy cơ ùn ứ vào khung giờ này"
      },
      {
        "minutes_ahead": 60,
        "target_time": "2026-11-14T18:00:00Z",
        "hour_of_day": 18,
        "day_of_week": 5,
        "predicted_speed": 13.2,
        "max_speed_limit": 50,
        "risk_factor": 0.74,
        "congestion_level": 4,
        "description": "Tắc nghẽn nghiêm trọng, nên chọn lộ trình tránh"
      }
    ],
    "updated_at": "2026-11-14T17:05:00Z"
  }
}
```

---

#### Quản trị viên (Admin Tasks)

##### `POST /api/v1/admin/retrain-model`
- **Mục đích**: Kích hoạt quy trình huấn luyện lại mô hình ML dự báo giao thông trong nền (**BackgroundTasks**).
- **Quyền hạn**: Bắt buộc tài khoản có quyền `role: "admin"`.
- **Giới hạn gọi**: Tối đa 2 lần / phút.
- **Cơ chế hoạt động**:
  1. API ngay lập tức phản hồi `200 OK` với trạng thái `processing`.
  2. Tiến trình nền chạy hàm `train_model()`: nạp dữ liệu từ `traffic_data`, huấn luyện mô hình mới, lưu phiên bản mới vào `ml_models` với `is_active=True`.
  3. Tự động gọi `PredictionService.reload_model()` để cập nhật mô hình mới vào RAM mà không cần restart máy chủ.
  4. Xóa cache giao thông `clear_traffic_data_cache()` để đồng bộ trạng thái mới nhất.

---

## 7. Luồng nghiệp vụ & Cơ chế xử lý chi tiết (Business Flows)

### Luồng 1: Xác thực JWT & Thu hồi Token tức thì (Token Revocation)

Hệ thống kết hợp ưu điểm của **Stateless Token** (không cần truy vấn DB mỗi request) và tính năng **Thu hồi Token ngay lập tức** khi có thay đổi bảo mật (đổi mật khẩu):

```mermaid
sequenceDiagram
    autonumber
    actor User as Người dùng
    participant API as Auth Endpoint
    participant Sec as Core Security
    participant DB as Database (User Table)

    Note over User,DB: Giai đoạn 1: Đăng nhập cấp Token
    User->>API: POST /api/v1/auth/login (email, password)
    API->>DB: Truy vấn user theo email
    DB-->>API: Trả về User (password_hash, role, token_version=1)
    API->>Sec: Xác thực Argon2 verify_password()
    Sec->>Sec: Tạo JWT với payload: {sub, role, token_version: 1}
    API-->>User: Trả về access_token

    Note over User,DB: Giai đoạn 2: Gọi API được bảo vệ
    User->>API: GET /api/v1/auth/me (Bearer Token)
    API->>Sec: get_current_user dependency
    Sec->>Sec: Giải mã JWT signature & expiry
    Sec->>DB: Kiểm tra: token.token_version == user.token_version?
    DB-->>Sec: Khớp phiên bản (1 == 1)
    API-->>User: 200 OK (Thông tin User)

    Note over User,DB: Giai đoạn 3: Đổi mật khẩu & Vô hiệu hóa Token
    User->>API: POST /api/v1/auth/change-password
    API->>DB: Cập nhật password_hash MỚI & tăng token_version = 2
    DB-->>API: Commit thành công
    API-->>User: 200 OK ("Đổi mật khẩu thành công")

    Note over User,DB: Giai đoạn 4: Kẻ xấu hoặc token cũ tiếp tục gọi
    User->>API: GET /api/v1/auth/me (với Token cũ chứa token_version=1)
    API->>Sec: get_current_user dependency
    Sec->>DB: Kiểm tra: 1 == 2? -> KHÔNG KHỚP!
    API-->>User: 401 Unauthorized ("Token đã bị vô hiệu hóa")
```

---

### Luồng 2: Giám sát trạng thái đường (Bounding Box & District Filter)

```mermaid
sequenceDiagram
    autonumber
    actor Client as Frontend Map Client
    participant Router as Edges Router
    participant Service as TrafficService
    participant Cache as In-Memory Cache (_TRAFFIC_DATA_CACHE)
    participant DB as Database (TrafficData / Edges / Nodes)

    Client->>Router: GET /api/v1/edges/status?bbox=...&district=Dong Da
    Router->>Router: parse_bbox_param() chuẩn hóa tọa độ (South, West, North, East)
    Router->>Router: Xác định hour & day_of_week hiện tại (Asia/Ho_Chi_Minh)
    Router->>Service: TrafficService.get_edges_status(...)
    
    Service->>DB: Lấy danh sách Edges nối với Nodes nằm trong BBox
    DB-->>Service: Danh sách Edges phù hợp
    
    alt district được truyền vào
        Service->>Service: strip_accents(district) lọc không dấu tiếng Việt
    end

    Service->>Cache: Lấy dữ liệu tốc độ lịch sử theo edge_code
    alt Cache chưa có trong RAM
        Cache->>DB: SELECT edge_code, hour, dow, speed FROM traffic_data
        DB-->>Cache: Đổ dữ liệu vào _TRAFFIC_DATA_CACHE
    end
    Cache-->>Service: Dữ liệu tốc độ theo giờ & ngày

    loop Với từng Edge
        Service->>Service: Tính toán tốc độ trung bình thực tế / mặc định
        Service->>Service: Quy đổi vận tốc sang congestion_level (1..4)
        Service->>Service: Gắn nhãn văn bản mô tả trạng thái
    end

    Service-->>Router: EdgeStatusResponse (total, edges list, filters)
    Router-->>Client: 200 OK Envelope
```

#### Quy tắc phân loại mức độ ùn tắc (`congestion_level`):
- **Cấp 1 - Thông thoáng** (Xanh lá): Vận tốc $\ge 35\text{ km/h}$.
- **Cấp 2 - Di chuyển chậm** (Vàng): $25\text{ km/h} \le$ Vận tốc $< 35\text{ km/h}$.
- **Cấp 3 - Ùn tắc nghiêm trọng** (Cam): $15\text{ km/h} \le$ Vận tốc $< 25\text{ km/h}$.
- **Cấp 4 - Kẹt xe hoàn toàn** (Đỏ): Vận tốc $< 15\text{ km/h}$.

---

### Luồng 3: Tìm đường tối ưu (Dijkstra trên NetworkX & Graph Cache)

```mermaid
sequenceDiagram
    autonumber
    actor Client as Client App
    participant Router as Directions Router
    participant Routing as RoutingService
    participant Cache as Graph Cache (_GRAPH_CACHE)
    participant DB as Database

    Client->>Router: GET /api/v1/directions?origin_node_id=...&destination_node_id=...&weight_mode=duration
    Router->>Routing: build_graph(session, weight_mode)

    alt Đồ thị đã có trong Cache và chưa quá TTL (300 giây)
        Routing->>Cache: Lấy đồ thị có sẵn
        Cache-->>Routing: TrafficGraph (MultiDiGraph)
    else Hết hạn hoặc lần đầu gọi
        Routing->>DB: Lấy toàn bộ Nodes & Edges hợp lệ
        DB-->>Routing: Dữ liệu mạng lưới
        Routing->>Routing: Dựng nx.MultiDiGraph()
        alt weight_mode == "duration"
            Routing->>Routing: Trọng số cạnh = (length_km / max_speed_limit) * 60 (phút)
        else weight_mode == "distance"
            Routing->>Routing: Trọng số cạnh = length_km (km)
        end
        Routing->>Cache: Lưu đồ thị vào _GRAPH_CACHE
    end

    Router->>Routing: find_route(graph, origin_node_id, destination_node_id)
    Routing->>Routing: nx.dijkstra_path(graph, origin, destination, weight="weight")
    Routing->>Routing: Trích xuất các bước đi (steps), tổng km, tổng phút di chuyển
    Routing->>Routing: Xây dựng tọa độ polyline [[lng, lat], ...]
    Routing-->>Router: RouteResult DTO
    Router-->>Client: 200 OK StandardResponse
```

---

### Luồng 4: Dự báo giao thông AI & Heuristic Fallback

Hệ thống đảm bảo tính sẵn sàng cao (**High Availability**): nếu chưa có mô hình AI hoặc mô hình gặp lỗi giải nén, dịch vụ tự động chuyển sang cơ chế suy nghiệm thông minh (**Heuristic Fallback**):

```mermaid
flowchart TD
    Start(["Nhận Request POST /forecast"]) --> Validate["Validate Input: edge_id/street_name, minutes_ahead, weather"]
    Validate --> FindEdge["Tìm kiếm Edge trong DB"]
    FindEdge --> FoundEdge{"Tìm thấy Edge?"}
    FoundEdge -- "Không" --> Return404["Ném lỗi HTTP 404 Not Found"]
    FoundEdge -- "Có" --> LoopMinutes["Lặp qua từng mốc thời gian: target_time = base_time + offset"]

    LoopMinutes --> CheckModel{"Có mô hình ML trong RAM?\n(_model is not None)"}

    subgraph AIPrediction ["Nhánh 1: Dự đoán qua Machine Learning"]
        CheckModel -- "Có" --> ExtractFeatures["Trích xuất Vector đặc trưng (7 features):\n[hour, day_of_week, is_weekend, is_rush_hour, weather_code, length_km, max_speed_limit]"]
        ExtractFeatures --> ModelPredict["model.predict(features)\nRandom Forest Regressor"]
    end

    subgraph HeuristicFallback ["Nhánh 2: Cơ chế Dự phòng Suy nghiệm"]
        CheckModel -- "Không" --> CalcFactor["Tính toán hệ số giảm tốc theo quy luật:\n- Giờ cao điểm ngày thường: giảm 45%\n- Giờ cao điểm cuối tuần: giảm 20%\n- Trời mưa: giảm thêm 15% - 30%"]
        CalcFactor --> HeuristicPredict["predicted_speed = max_speed_limit * factor"]
    end

    ModelPredict --> NormalizeSpeed["Chuẩn hóa vận tốc: clamp(5.0 km/h, max_speed_limit)"]
    HeuristicPredict --> NormalizeSpeed

    NormalizeSpeed --> CalcRisk["Tính toán chỉ số rủi ro:\nrisk_factor = 1.0 - (predicted_speed / max_speed_limit)"]
    CalcRisk --> AssignLevel["Phân cấp ùn tắc (1-4) & gắn mô tả trực quan"]
    AssignLevel --> NextMinute{"Còn mốc phút tiếp theo?"}
    NextMinute -- "Còn" --> LoopMinutes
    NextMinute -- "Hết" --> ReturnResponse["Trả về PredictionResponse Envelope (timeline đầy đủ)"]
```

---

### Luồng 5: Huấn luyện lại mô hình trong tiến trình ngầm (Background Task)

```mermaid
flowchart TD
    AdminUser(["Admin gọi POST /api/v1/admin/retrain-model"]) --> VerifyAdmin{"Xác thực role == 'admin'?"}
    VerifyAdmin -- "Không" --> Deny["Trả về 403 Forbidden"]
    VerifyAdmin -- "Đúng" --> AddBgTask["Thêm tác vụ _run_retraining() vào BackgroundTasks"]
    AddBgTask --> ReturnFast["Phản hồi ngay 200 OK: 'Model training running in background'"]

    subgraph BackgroundExecution ["Tiến trình nền (Background Execution)"]
        RunTrain["scripts/train_prediction_model.py: train_model()"]
        RunTrain --> QueryDB["Đọc ma trận dữ liệu từ bảng traffic_data"]
        QueryDB --> FitModel["Huấn luyện RandomForestRegressor(n_estimators=40, max_depth=10)"]
        FitModel --> Eval["Đánh giá R2 Score & chỉ số độ chính xác"]
        Eval --> Serialize["Chuyển mô hình thành bytes (joblib.dump sang BytesIO)"]
        Serialize --> SaveDB["Lưu bản ghi MLModel mới vào DB:\n- Đánh dấu các bản ghi cũ: is_active = False\n- Ghi bản ghi mới: is_active = True, version += 1"]
        SaveDB --> ReloadMem["PredictionService.reload_model():\nNạp bytes mới vào RAM dưới Thread-Lock"]
        ReloadMem --> ClearCache["clear_traffic_data_cache():\nXóa cache dữ liệu giao thông cũ"]
        ClearCache --> Done["Hoàn tất huấn luyện và đồng bộ hệ thống"]
    end

    AddBgTask -. Kích hoạt .-> RunTrain
```

---

## 8. Bảo mật & Giới hạn tần suất (Rate Limiting)

Hệ thống áp dụng kiến trúc bảo vệ nhiều lớp nhằm chống tấn công DoS, Brute-force và rò rỉ thông tin nhạy cảm:

### 8.1. Ma trận giới hạn tần suất (Rate Limiting Matrix)
Được cấu hình thông qua thư viện **SlowAPI**:

| Endpoint | Giới hạn gọi | Mục đích phòng thủ |
| :--- | :--- | :--- |
| `/api/v1/auth/register` | `5/minute` | Chống spam tạo tài khoản rác |
| `/api/v1/auth/login` | `5/minute` | Chống tấn công dò mật khẩu (Brute-force) |
| `/api/v1/auth/change-password` | `5/minute` | Bảo vệ tài khoản người dùng |
| `/api/v1/admin/retrain-model` | `2/minute` | Chống quá tải CPU/RAM khi huấn luyện AI |
| `/api/v1/predictions/forecast` | `10/minute` | Tối ưu hóa tài nguyên tính toán inference |
| `/api/v1/directions` | `20/minute` | Tránh nghẽn tính toán Dijkstra liên tục |
| `/api/v1/edges/status` | `60/minute` | Hỗ trợ polling cập nhật bản đồ thời gian thực |

### 8.2. Các cơ chế bảo mật bổ sung
1. **Mã hóa mật khẩu bằng Argon2**: Sử dụng thuật toán đạt giải nhất cuộc thi Password Hashing Competition (PHC), chống tấn công bằng GPU/FPGA.
2. **Kiểm tra độ an toàn cấu hình Production**: Khi khởi chạy ở môi trường ngoài `dev`, hệ thống tự động kiểm tra và chặn khởi động nếu `JWT_SECRET_KEY` còn mang giá trị mặc định hoặc độ dài dưới 32 ký tự.
3. **Che giấu lỗi hệ thống (Safe Error Disclosure)**: API `/api/health` và các handler không làm lộ chuỗi kết nối cơ sở dữ liệu hay stack trace nội bộ ra ngoài Client.

---

## 9. Các Scripts tiện ích (CLI Utilities)

Trong thư mục `scripts/`, dự án cung cấp sẵn các công cụ dòng lệnh hỗ trợ thiết lập và vận hành:

### 1. `scripts/seed_hanoi_network.py`
Nạp danh sách các nút giao thông tiêu biểu tại Hà Nội (Ngã tư Sở, Cầu Giấy, Khuất Duy Tiến, Kim Mã, v.v.) và các cung đường kết nối giữa chúng vào cơ sở dữ liệu.
```bash
uv run python scripts/seed_hanoi_network.py
```

### 2. `scripts/import_traffic_csv_to_db.py`
Chuyển đổi dữ liệu giao thông lịch sử từ file CSV vào bảng database `traffic_data` theo từng lô (batch insert 1000 bản ghi/lần).
```bash
# Xóa sạch dữ liệu cũ và nạp mới toàn bộ
uv run python scripts/import_traffic_csv_to_db.py --csv-path data/synthetic_traffic_dataset.csv --truncate

# Nạp thêm dữ liệu (append)
uv run python scripts/import_traffic_csv_to_db.py --csv-path data/synthetic_traffic_dataset.csv
```

### 3. `scripts/train_prediction_model.py`
Đọc trực tiếp dữ liệu huấn luyện từ bảng `traffic_data` trong database, huấn luyện `RandomForestRegressor`, đánh giá chỉ số và lưu trực tiếp nhị phân mô hình vào bảng `ml_models`.
```bash
uv run python scripts/train_prediction_model.py
```

### 4. `scripts/generate_synthetic_traffic.py`
Sinh dữ liệu mô phỏng giao thông lớn dựa trên các phân phối thực tế (giờ cao điểm, ngày cuối tuần, điều kiện thời tiết).
```bash
uv run python scripts/generate_synthetic_traffic.py --rows 10000 --output data/synthetic_traffic_dataset.csv
```

---

## 10. Kiểm thử tự động (Testing)

Dự án sở hữu bộ kiểm thử tự động toàn diện bao quát các module từ Core, Security, Database Models, Services cho đến Endpoints E2E:

```bash
# Chạy toàn bộ 30 bài kiểm thử với pytest qua uv
uv run --with pytest python -m pytest -v
```

### Danh sách các kịch bản kiểm thử:
- `tests/test_admin_retrain_e2e.py`: Kiểm thử luồng E2E gọi API Admin retrain model chạy ngầm.
- `tests/test_auth_token_revocation.py`: Kiểm thử cơ chế vô hiệu hóa Access Token tức thì khi đổi mật khẩu qua `token_version`.
- `tests/test_config_security.py`: Kiểm tra cơ chế tự động từ chối cấu hình insecure JWT secret trên production.
- `tests/test_db_models.py`: Kiểm tra schema, ràng buộc khóa ngoại CASCADE và tính toàn vẹn của các thực thể SQLModel.
- `tests/test_health_disclosure.py`: Đảm bảo health check không làm rò rỉ thông tin nhạy cảm của hệ thống.
- `tests/test_import_csv.py`: Kiểm thử script import dữ liệu CSV theo batch và truncate table.
- `tests/test_prediction_security.py`: Validate chặt chẽ dữ liệu đầu vào của API dự báo (giới hạn minutes_ahead).
- `tests/test_prediction_service_db.py`: Kiểm thử nạp model từ database và cơ chế heuristic fallback khi DB chưa có model.
- `tests/test_routing_cache.py`: Kiểm thử bộ nhớ đệm đồ thị NetworkX theo TTL.
- `tests/test_security_jwt.py`: Kiểm thử mã hóa và giải mã JWT token roundtrip.
- `tests/test_traffic_service_db.py`: Kiểm tra tính toán snapshot trạng thái giao thông trực tiếp từ bảng `traffic_data`.
- `tests/test_train_prediction_model.py`: Kiểm thử huấn luyện mô hình và lưu BLOB vào `ml_models`.
