# 🚦 Traffic System Backend (BE)

Hệ thống API Backend thông minh phục vụ **giám sát thời gian thực**, **định tuyến tìm đường tối ưu**, **dự báo tình trạng ùn tắc giao thông tương lai** và **Trợ lý Chatbot AI thông minh với mã hóa đầu cuối (E2E Encrypted AI Chatbot)**. Được xây dựng trên nền tảng **FastAPI**, **SQLModel / SQLAlchemy 2.0**, **NetworkX**, **Scikit-learn**, **Google Gemini API** và thư viện mật mã **Cryptography (ECDH X25519 + AES-256-GCM)**.

---

## 📑 Mục lục
- [1. Tổng quan kiến trúc hệ thống](#1-tổng-quan-kiến-trúc-hệ-thống)
- [2. Sơ đồ cơ sở dữ liệu (Database Schema & ERD)](#2-sơ-đồ-cơ-sở-dữ-liệu-database-schema--erd)
  - [2.1. Sơ đồ thực thể quan hệ (ERD)](#21-sơ-đồ-thực-thể-quan-hệ-erd)
  - [2.2. Điểm kiến trúc cốt lõi của Database](#22-điểm-kiến-trúc-cốt-lõi-của-database)
- [3. Hướng dẫn cài đặt & Khởi chạy](#3-hướng-dẫn-cài-đặt--khởi-chạy)
- [4. Cấu trúc thư mục dự án](#4-cấu-trúc-thư-mục-dự-án)
- [5. Chuẩn hóa API & Envelope Response](#5-chuẩn-hóa-api--envelope-response)
- [6. Danh mục API chi tiết (Endpoints Reference)](#6-danh-mục-api-chi-tiết-endpoints-reference)
  - [Bảng tóm tắt các Endpoints](#bảng-tóm-tắt-các-endpoints)
  - [Hệ thống & Health Check](#hệ-thống--health-check)
  - [Xác thực & Phân quyền (Auth & RBAC)](#xác-thực--phân-quyền-auth--rbac)
  - [Giám sát & Quản lý cung đường (Edges & Traffic Status)](#giám-sát--quản-lý-cung-đường-edges--traffic-status)
  - [Tìm đường thông minh (Directions & Routing)](#tìm-đường-thông-minh-directions--routing)
  - [Dự báo giao thông AI (Predictions & Forecast)](#dự-báo-giao-thông-ai-predictions--forecast)
  - [Trợ lý Chatbot AI Mã hóa E2E (Chatbot AI & Gemini)](#trợ-lý-chatbot-ai-mã-hóa-e2e-chatbot-ai--gemini)
  - [Quản trị viên (Admin Tasks)](#quản-trị-viên-admin-tasks)
- [7. Luồng nghiệp vụ & Cơ chế xử lý chi tiết (Business Flows)](#7-luồng-nghiệp-vụ--cơ-chế-xử-lý-chi-tiết-business-flows)
  - [Luồng 1: Xác thực JWT & Thu hồi Token tức thì (Token Revocation)](#luồng-1-xác-thực-jwt--thu-hồi-token-tức-thì-token-revocation)
  - [Luồng 2: Giám sát trạng thái đường (Bounding Box & District Filter)](#luồng-2-giám-sát-trạng-thái-đường-bounding-box--district-filter)
  - [Luồng 3: Tìm đường tối ưu (Dijkstra trên NetworkX & Graph Cache)](#luồng-3-tìm-đường-tối-ưu-dijkstra-trên-networkx--graph-cache)
  - [Luồng 4: Dự báo giao thông AI & Heuristic Fallback](#luồng-4-dự-báo-giao-thông-ai--heuristic-fallback)
  - [Luồng 5: Huấn luyện lại mô hình trong tiến trình ngầm (Background Task)](#luồng-5-huấn-luyện-lại-mô-hình-trong-tiến-trình-ngầm-background-task)
  - [Luồng 6: Trò chuyện AI với Mã hóa E2E & Đồng bộ Đa thiết bị (Dual-Envelope Key Agreement)](#luồng-6-trò-chuyện-ai-với-mã-hóa-e2e--đồng-bộ-đa-thiết-bị-dual-envelope-key-agreement)
- [8. Bảo mật & Giới hạn tần suất (Rate Limiting & Cryptography)](#8-bảo-mật--giới-hạn-tần-suất-rate-limiting--cryptography)
  - [8.1. Ma trận giới hạn tần suất (SlowAPI)](#81-ma-trận-giới-hạn-tần-suất-slowapi)
  - [8.2. Kiến trúc Mật mã Đầu Cuối (E2E Cryptography) & Zero-Knowledge Storage](#82-kiến-trúc-mật-mã-đầu-cuối-e2e-cryptography--zero-knowledge-storage)
  - [8.3. Các cơ chế bảo mật bổ sung](#83-các-cơ-chế-bảo-mật-bổ-sung)
- [9. Các Scripts tiện ích (CLI Utilities)](#9-các-scripts-tiện-ích-cli-utilities)
- [10. Kiểm thử tự động (Testing)](#10-kiểm-thử-tự-động-testing)

---

## 1. Tổng quan kiến trúc hệ thống

Hệ thống được thiết kế theo mô hình phân lớp hiện đại (**Layered Architecture**), tách biệt rõ ràng giữa Controller/Endpoints, Service Layer, Core Components và Data Layer:

```mermaid
flowchart TD
    Client["Client (Web App / Mobile / Postman / CLI Demo)"] --> RateLimiter["SlowAPI Rate Limiter"]
    RateLimiter --> CORSMiddleware["CORS Middleware"]
    CORSMiddleware --> ExceptionHandler["Global Exception Handlers"]
    
    subgraph APILayer ["API Layer (FastAPI Routers)"]
        R_Auth["/api/v1/auth\n(Register, Login, Me, Change Password)"]
        R_Edges["/api/v1/edges\n(Realtime Status, BBox, CRUD)"]
        R_Directions["/api/v1/directions\n(Shortest & Fastest Dijkstra)"]
        R_Predictions["/api/v1/predictions\n(Timeline Traffic Forecast)"]
        R_Chat["/api/v1/chat\n(E2E Encrypted AI Chatbot)"]
        R_Admin["/api/v1/admin\n(Background ML Retraining)"]
        R_System["/api/health & /api/data"]
    end
    ExceptionHandler --> APILayer

    subgraph ServiceAndCoreLayer ["Service & Core Components"]
        S_Auth["AuthService\n(Argon2, JWT, Token Versioning)"]
        S_Traffic["TrafficService\n(Traffic DB Cache, BBox, District Matcher)"]
        S_Routing["RoutingService\n(NetworkX Graph, Dijkstra Routing)"]
        S_Predict["PredictionService\n(RandomForest, Timeline, Fallback)"]
        S_Gemini["GeminiService\n(Multi-turn AI Assistant via REST API)"]
        C_Crypto["Crypto Engine\n(ECDH X25519, AES-256-GCM, PBKDF2, HKDF)"]
    end
    
    R_Auth --> S_Auth
    R_Edges --> S_Traffic
    R_Directions --> S_Routing
    R_Predictions --> S_Predict
    R_Chat --> C_Crypto
    R_Chat --> S_Gemini
    R_Admin --> S_Predict
    R_Admin --> S_Traffic

    subgraph StorageAndExternal ["Storage & External Engines"]
        DB[("Database\n(PostgreSQL Supabase / SQLite)")]
        TrafficCache[("In-Memory Traffic Cache\n(Thread-Safe Lock)")]
        GraphCache[("In-Memory Graph Cache\n(TTL 300s)")]
        MLMemory[("In-Memory ML Model\n(joblib deserialized)")]
        Ext_Gemini[("Google Gemini 2.5 Flash\n(Google GenAI REST API)")]
    end

    S_Auth <--> DB
    S_Traffic <--> DB
    S_Traffic <--> TrafficCache
    S_Routing <--> DB
    S_Routing <--> GraphCache
    S_Predict <--> DB
    S_Predict <--> MLMemory
    R_Chat <--> DB
    S_Gemini <--> Ext_Gemini
```

---

## 2. Sơ đồ cơ sở dữ liệu (Database Schema & ERD)

Hệ thống sử dụng **SQLModel** (xây dựng trên SQLAlchemy 2.0). Dữ liệu hỗ trợ linh hoạt cả **SQLite** (cho môi trường local dev/kiểm thử tự động) và **PostgreSQL / Supabase** (môi trường production).

### 2.1. Sơ đồ thực thể quan hệ (ERD)

```mermaid
erDiagram
    NODES ||--o{ EDGES : "from_node (CASCADE)"
    NODES ||--o{ EDGES : "to_node (CASCADE)"
    EDGES ||--o{ PREDICTIONS : "edge_id (CASCADE)"
    USERS ||--o{ CHAT_SESSIONS : "user_id (CASCADE)"
    CHAT_SESSIONS ||--o{ CHAT_MESSAGES : "session_id (CASCADE)"

    USERS {
        uuid user_id PK "UUIDv4 khóa chính"
        string email UK "Email độc nhất, max 100"
        string password_hash "Mật khẩu băm Argon2"
        string full_name "Họ và tên người dùng"
        string role "Vai trò: user / admin"
        int token_version "Phiên bản token kiểm soát thu hồi"
        string encryption_salt "Muối dẫn xuất User Master Key (Base64)"
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

    CHAT_SESSIONS {
        uuid id PK "UUIDv4 khóa chính"
        uuid user_id FK "FK tham chiếu USERS.user_id (CASCADE)"
        string title_encrypted "Ciphertext tiêu đề phiên chat (Base64)"
        string title_nonce "Nonce 12-byte của tiêu đề (Base64)"
        string session_key_enc_user "K_session mã hóa bằng User Master Key"
        string session_key_nonce_user "Nonce giải mã K_session cho User"
        string session_key_enc_server "K_session mã hóa bằng Server Secret"
        string session_key_nonce_server "Nonce giải mã K_session cho Server"
        datetime created_at "Thời điểm tạo phiên chat (UTC)"
        datetime updated_at "Thời điểm hoạt động gần nhất (UTC)"
    }

    CHAT_MESSAGES {
        uuid id PK "UUIDv4 khóa chính"
        uuid session_id FK "FK tham chiếu CHAT_SESSIONS.id (CASCADE)"
        string role "Vai trò: 'user' hoặc 'model'"
        string ciphertext "Nội dung tin nhắn mã hóa AES-256-GCM (Base64)"
        string nonce "12-byte Nonce độc nhất chống Replay (Base64)"
        datetime created_at "Thời điểm gửi tin nhắn (UTC)"
    }
```

### 2.2. Điểm kiến trúc cốt lõi của Database

1. **Quản lý mô hình ML trong Database (`ml_models`)**: Thay vì phụ thuộc vào file tĩnh trên đĩa (`.joblib`), các mô hình sau khi huấn luyện được lưu dưới dạng nhị phân (`LargeBinary BLOB`). Hệ thống truy vấn phiên bản có `is_active=True` và `version` cao nhất để nạp trực tiếp vào RAM.
2. **Loại bỏ phụ thuộc file CSV tĩnh (`traffic_data`)**: Mọi dữ liệu lịch sử giao thông phục vụ huấn luyện AI và tính toán trạng thái giao thông đều được quản lý tập trung và đánh chỉ mục trong bảng `traffic_data`.
3. **Cơ chế thu hồi Token tức thời (`token_version` trong `users`)**: Cho phép thu hồi toàn bộ token của tài khoản ngay lập tức khi người dùng đổi mật khẩu mà không cần triển khai blacklist Redis phức tạp.
4. **Mã hóa E2E & Lưu trữ Zero-Knowledge cho Chatbot (`chat_sessions`, `chat_messages`)**:
   - Toàn bộ nội dung câu hỏi của người dùng, phản hồi của Gemini AI và tiêu đề phiên đều được lưu trữ dưới dạng **Ciphertext + Nonce** (AES-256-GCM). Cơ sở dữ liệu tuyệt đối không chứa văn bản thô (Plaintext).
   - Cơ chế **Dual-Envelope Session Key**: Khóa phiên $K_{session}$ được bọc 2 lớp riêng biệt: một lớp mã hóa bằng `User Master Key` (giúp đồng bộ đa thiết bị khi người dùng đăng nhập từ máy mới) và một lớp mã hóa bằng `Server App Secret` (cho phép Server giải mã tạm thời trong RAM khi tương tác với Gemini).
   - Ràng buộc độc nhất cấp cơ sở dữ liệu `UNIQUE(session_id, nonce)` ngăn chặn hoàn toàn tấn công phát lại (Replay Attack) và bảo vệ an toàn cho bộ sinh dòng khóa AES-GCM.

---

## 3. Hướng dẫn cài đặt & Khởi chạy

### 3.1. Yêu cầu hệ thống
- **Python**: Phiên bản `>= 3.14` (hoặc Python 3.12+)
- **Trình quản lý gói**: Khuyến nghị dùng [uv](https://docs.astral.sh/uv/) (hoặc `pip` / `venv` chuẩn)
- **Hệ điều hành**: Linux, macOS hoặc Windows

### 3.2. Cài đặt môi trường

Sử dụng **uv** (nhanh và chuẩn xác nhất):
```bash
# Clone repository
git clone https://github.com/HungNguyen254/TRAFFIC_SYSTEM_BE.git
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

# Giới hạn tần suất gọi API (SlowAPI)
RATE_LIMIT_ENABLED=True
RATE_LIMIT_DEFAULT="60/minute"

# Tích hợp Chatbot AI & Mật mã (Google Gemini & E2E Crypto)
# Lấy khóa miễn phí tại: https://aistudio.google.com/
GEMINI_API_KEY="your-google-gemini-api-key"
GEMINI_MODEL="gemini-2.5-flash"
# Khóa Server Master (Base64 chuỗi 32 byte). Để trống hệ thống sẽ tự sinh ngẫu nhiên khi khởi động
CHAT_MASTER_KEY=""
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
- **Tài liệu Swagger UI tương tác**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
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
│   │       │   ├── chat.py           # API Chatbot AI E2E (Handshake, Message, Sessions)
│   │       │   ├── directions.py     # API tìm đường tối ưu (Dijkstra)
│   │       │   ├── edges.py          # API trạng thái đường & CRUD Edges
│   │       │   └── predictions.py    # API dự báo tình trạng giao thông tương lai
│   │       └── router.py             # Tổng hợp các endpoint v1
│   ├── core/
│   │   ├── config.py                 # Cấu hình Pydantic BaseSettings & validate môi trường
│   │   ├── crypto.py                 # Mật mã E2E (ECDH X25519, AES-256-GCM, PBKDF2, HKDF)
│   │   ├── database.py               # Kết nối cơ sở dữ liệu, SessionDep, schema auto-patch
│   │   ├── exceptions.py             # Định nghĩa mã lỗi tùy chỉnh (AppException)
│   │   ├── handlers.py               # Xử lý ngoại lệ tập trung (Centralized Exception Handlers)
│   │   ├── limiter.py                # Cấu hình Rate Limiter (SlowAPI)
│   │   ├── response.py               # Cấu trúc envelope StandardResponse chuẩn hóa
│   │   └── security.py               # Băm mật khẩu Argon2, tạo/giải mã JWT, RBAC dependencies
│   ├── middlewares/
│   │   └── middleware.py             # Cấu hình CORS middleware
│   ├── models/                       # Các thực thể dữ liệu SQLModel (Database Tables)
│   │   ├── chat.py                   # Bảng ChatSession & ChatMessage
│   │   ├── edge.py                   # Cung đường nối 2 nút giao
│   │   ├── ml_model.py               # Bản ghi nhị phân mô hình ML
│   │   ├── node.py                   # Nút giao thông
│   │   ├── prediction.py             # Dữ liệu dự báo theo giờ
│   │   ├── traffic_data.py           # Bản ghi dữ liệu giao thông lịch sử
│   │   └── user.py                   # Tài khoản người dùng, RBAC & encryption_salt
│   ├── schemas/                      # Pydantic Schemas (Request Payload & Response DTO)
│   │   ├── auth.py
│   │   ├── chat.py
│   │   ├── edge_status.py
│   │   ├── prediction.py
│   │   ├── routing.py
│   │   └── traffic.py
│   ├── services/                     # Lớp xử lý nghiệp vụ chính (Business Logic Layer)
│   │   ├── auth_service.py           # Nghiệp vụ đăng ký, xác thực, đổi mật khẩu
│   │   ├── gemini_service.py         # Gọi Google Gemini REST API đa lượt hội thoại
│   │   ├── prediction_service.py     # Nạp mô hình ML từ DB, dự báo timeline, fallback
│   │   ├── routing_service.py        # Dựng đồ thị NetworkX, chạy thuật toán Dijkstra
│   │   └── traffic_service.py        # Tính toán snapshot tốc độ, lọc BBox / District
│   └── main.py                       # Điểm khởi chạy FastAPI, Lifespan kết nối DB & nạp model
├── data/
│   └── synthetic_traffic_dataset.csv # File dữ liệu giao thông mẫu dự phòng
├── docs/                             # Tài liệu kiến trúc và kế hoạch thực thi (Superpowers)
│   ├── README.md                     # Mục lục tài liệu thiết kế và kế hoạch
│   └── superpowers/                  # Specs và Plans chi tiết
├── scripts/                          # Bộ công cụ dòng lệnh (CLI Utilities)
│   ├── README.md                     # Hướng dẫn chi tiết sử dụng các scripts
│   ├── chat_e2e_client_demo.py       # Demo Client E2E mã hóa + đa thiết bị
│   ├── generate_synthetic_traffic.py # Sinh dữ liệu giao thông giả lập
│   ├── import_traffic_csv_to_db.py   # Nhập dữ liệu CSV vào bảng traffic_data
│   ├── seed_hanoi_network.py         # Nạp các nút giao và cung đường mẫu Hà Nội
│   └── train_prediction_model.py     # Huấn luyện Random Forest & lưu vào bảng ml_models
├── tests/                            # Bộ kiểm thử tự động toàn diện (48 tests, 100% PASS)
│   └── README.md                     # Hướng dẫn kiểm thử và mô tả từng module test
├── .env.example                      # File mẫu biến môi trường chuẩn
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
  "path": "/api/v1/chat/sessions",
  "timestamp": "2026-11-15T15:30:00.000000Z"
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
  "timestamp": "2026-11-15T15:30:00.000000Z"
}
```

---

## 6. Danh mục API chi tiết (Endpoints Reference)

### Bảng tóm tắt các Endpoints

| Nhóm | Phương thức | Đường dẫn | Quyền hạn | Giới hạn (Rate Limit) | Mục đích chính |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **System** | `GET` | `/api/data` | Public | - | Lời chào mừng và xác nhận API hoạt động |
| | `GET` | `/api/health` | Public | - | Kiểm tra sức khỏe máy chủ & trạng thái kết nối DB |
| **Auth** | `POST` | `/api/v1/auth/register` | Public | 5 req/phút | Đăng ký tài khoản người dùng mới (Argon2) |
| | `POST` | `/api/v1/auth/login` | Public | 5 req/phút | Đăng nhập nhận Access Token (JWT) |
| | `GET` | `/api/v1/auth/me` | Bearer Token | - | Lấy thông tin tài khoản hiện tại |
| | `POST` | `/api/v1/auth/change-password` | Bearer Token | 5 req/phút | Đổi mật khẩu & vô hiệu hóa ngay token cũ |
| **Edges** | `GET` | `/api/v1/edges/status` | Public | 60 req/phút | Lấy tình trạng tắc đường theo BBox / Quận |
| | `GET` | `/api/v1/edges` | Public | 30 req/phút | Lấy danh sách nodes & edges kèm mức tắc |
| | `GET` | `/api/v1/edges/{edge_id}` | Public | - | Lấy chi tiết thông tin một đoạn đường |
| | `POST` | `/api/v1/edges` | **Admin** | - | Tạo mới một đoạn đường |
| | `PUT` | `/api/v1/edges/{edge_id}` | **Admin** | - | Cập nhật thông tin đoạn đường |
| | `DELETE`| `/api/v1/edges/{edge_id}` | **Admin** | - | Xóa đoạn đường khỏi hệ thống |
| **Routing**| `GET` | `/api/v1/directions` | Public | 20 req/phút | Tìm đường tối ưu (`distance` hoặc `duration`) |
| **Predict**| `POST` | `/api/v1/predictions/forecast`| Public | 10 req/phút | Dự báo dòng thời gian tắc đường tương lai |
| **Chat AI**| `GET` | `/api/v1/chat/user-salt` | Bearer Token | 60 req/phút | Lấy User Salt & Public Key Server phục vụ E2E |
| | `POST` | `/api/v1/chat/handshake` | Bearer Token | 20 req/phút | Bắt tay ECDH X25519 & tạo phiên trò chuyện |
| | `POST` | `/api/v1/chat/message` | Bearer Token | 30 req/phút | Gửi tin nhắn mã hóa E2E & nhận trả lời Gemini AI |
| | `GET` | `/api/v1/chat/sessions` | Bearer Token | 60 req/phút | Lấy danh sách phiên chat (kèm User Session Key) |
| | `PATCH` | `/api/v1/chat/sessions/{session_id}` | Bearer Token | 30 req/phút | Cập nhật tiêu đề mã hóa cho phiên chat |
| | `GET` | `/api/v1/chat/sessions/{session_id}/messages`| Bearer Token | 60 req/phút | Lấy toàn bộ lịch sử tin nhắn mã hóa của phiên |
| | `DELETE`| `/api/v1/chat/sessions/{session_id}` | Bearer Token | 20 req/phút | Xóa phiên chat và các tin nhắn liên quan |
| **Admin** | `POST` | `/api/v1/admin/retrain-model` | **Admin** | 2 req/phút | Kích hoạt huấn luyện lại mô hình AI ngầm |

---

### Chi tiết các API

#### Hệ thống & Health Check

##### 1. `GET /api/health`
- **Mục đích**: Kiểm tra tình trạng máy chủ và kết nối cơ sở dữ liệu an toàn.
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
  "timestamp": "2026-11-15T15:30:00Z"
}
```

---

#### Xác thực & Phân quyền (Auth & RBAC)

##### 1. `POST /api/v1/auth/register`
- **Mục đích**: Đăng ký người dùng mới. Mật khẩu được băm bằng **Argon2**, tự động sinh `encryption_salt` cho E2E Cryptography.
- **Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "Nguyễn Văn A"
}
```

##### 2. `POST /api/v1/auth/login`
- **Mục đích**: Xác thực người dùng và cấp JWT Access Token (chứa `sub`, `role`, `token_version`).
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
- **Mục đích**: Đổi mật khẩu. Tăng `token_version` trong database để **lập tức vô hiệu hóa mọi access token cũ**.

---

#### Giám sát & Quản lý cung đường (Edges & Traffic Status)

##### 1. `GET /api/v1/edges/status`
- **Mục đích**: Trả về tình trạng giao thông thời gian thực của các đoạn đường.
- **Query Params**:
  - `bbox`: Chuỗi khung nhìn `"min_lng,min_lat,max_lng,max_lat"` hoặc `"min_lat,min_lng,max_lat,max_lng"`.
  - Hoặc 4 tham số: `min_lat`, `min_lng`, `max_lat`, `max_lng`.
  - `district`: Lọc theo Quận/Huyện (vd: `Đống Đa`, `Cau Giay` — **hỗ trợ tìm kiếm tiếng Việt không dấu, không phân biệt hoa thường**).
  - `hour`: Khung giờ (0-23, mặc định giờ hiện tại theo múi giờ `Asia/Ho_Chi_Minh`).
  - `day_of_week`: Thứ (0: Thứ 2 ... 6: Chủ Nhật).
- **Ví dụ gọi**:
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/edges/status?district=Dong%20Da&hour=18"
```

##### 2. `GET /api/v1/edges`
- **Mục đích**: Trả về dữ liệu kết hợp cả danh sách `nodes` và `edges` kèm thông số giao thông phục vụ hiển thị lớp phủ bản đồ (Map Overlay).

##### 3. Quản lý Cung đường (CRUD Edges - Quyền Admin)
- `POST /api/v1/edges`: Tạo đoạn đường mới.
- `GET /api/v1/edges/{edge_id}`: Xem chi tiết đoạn đường.
- `PUT /api/v1/edges/{edge_id}`: Cập nhật thông tin đoạn đường.
- `DELETE /api/v1/edges/{edge_id}`: Xóa đoạn đường.

---

#### Tìm đường thông minh (Directions & Routing)

##### `GET /api/v1/directions`
- **Mục đích**: Tìm lộ trình tối ưu bằng thuật toán Dijkstra trên đồ thị đa hướng có hướng (`nx.MultiDiGraph`) kết hợp In-Memory Cache (TTL 300s).
- **Query Params**:
  - `origin_node_id` (UUID): ID của nút giao xuất phát.
  - `destination_node_id` (UUID): ID của nút giao đích.
  - `weight_mode`: Chế độ tối ưu:
    - `"distance"`: Ưu tiên quãng đường ngắn nhất (tổng km nhỏ nhất).
    - `"duration"`: Ưu tiên thời gian di chuyển nhanh nhất (phút).
- **Ví dụ gọi**:
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/directions?origin_node_id=11111111-1111-1111-1111-111111111111&destination_node_id=22222222-2222-2222-2222-222222222222&weight_mode=duration"
```

---

#### Dự báo giao thông AI (Predictions & Forecast)

##### `POST /api/v1/predictions/forecast`
- **Mục đích**: Dự đoán tốc độ di chuyển, chỉ số rủi ro và mức độ tắc nghẽn theo dòng thời gian tương lai (sau 30p, 60p, 120p...) qua mô hình **Random Forest Regressor** (hoặc Heuristic Fallback).
- **Request Body**:
```json
{
  "edge_id": "7ac18c89-c439-4d64-8898-75b8e97f0eb9",
  "base_time": "2026-11-15T17:00:00Z",
  "minutes_ahead": [30, 60, 120],
  "weather": "rain"
}
```

---

#### Trợ lý Chatbot AI Mã hóa E2E (Chatbot AI & Gemini)

Toàn bộ các endpoint dưới đây đều yêu cầu xác thực JWT (`Authorization: Bearer <token>`).

##### 1. `GET /api/v1/chat/user-salt`
- **Mục đích**: Lấy `encryption_salt` của người dùng để client dẫn xuất `User Master Key` (UMK) qua PBKDF2, đồng thời nhận `server_public_key` (X25519) phục vụ handshake.
- **Dữ liệu trả về**:
```json
{
  "status_code": 200,
  "message": "Lấy salt và server public key thành công",
  "data": {
    "encryption_salt": "k76Jk+32rgUaLXlso+kq7w==",
    "server_public_key": "h60b5zgCebQiJUnuSdgR89+MOEa84xYoc9e2lN+gzCM="
  }
}
```

##### 2. `POST /api/v1/chat/handshake`
- **Mục đích**: Khởi tạo phiên trò chuyện mới. Client gửi `client_public_key` (X25519) và khóa đối xứng phiên đã bọc bằng UMK (`session_key_enc_user`). Hai bên độc lập tính toán khóa đối xứng phiên $K_{session}$ qua ECDH X25519 và HKDF-SHA256.
- **Request Body**:
```json
{
  "client_public_key": "Base64(32-byte-X25519-public-key)",
  "title_encrypted": "Base64(Ciphertext tiêu đề)",
  "title_nonce": "Base64(12-byte nonce tiêu đề)",
  "session_key_enc_user": "Base64(K_session được mã hóa bằng UMK)",
  "session_key_nonce_user": "Base64(12-byte nonce UMK)"
}
```
- **Dữ liệu trả về**:
```json
{
  "status_code": 200,
  "message": "Khởi tạo phiên chat thành công",
  "data": {
    "session_id": "71f61c99-743c-4490-b694-f18a51acecd0",
    "server_public_key": "h60b5zgCebQiJUnuSdgR89+MOEa84xYoc9e2lN+gzCM="
  }
}
```

##### 3. `POST /api/v1/chat/message`
- **Mục đích**: Gửi tin nhắn mã hóa đầu cuối. Server kiểm tra chống nonce reuse, giải mã tạm thời trong RAM, nạp lịch sử hội thoại gần nhất, gọi Google Gemini API, mã hóa câu trả lời bằng $K_{session}$ và lưu trữ ciphertext vào cơ sở dữ liệu.
- **Request Body**:
```json
{
  "session_id": "71f61c99-743c-4490-b694-f18a51acecd0",
  "ciphertext": "Base64(AES-256-GCM encrypted JSON payload)",
  "nonce": "Base64(12-byte random unique nonce)"
}
```
*(Trong đó JSON payload được mã hóa có dạng `{"content": "Tình hình giao thông hiện tại ra sao?", "timestamp": "..."}`)*.
- **Dữ liệu trả về**:
```json
{
  "status_code": 200,
  "message": "Nhận phản hồi từ AI thành công",
  "data": {
    "session_id": "71f61c99-743c-4490-b694-f18a51acecd0",
    "ciphertext": "Base64(Phản hồi mã hóa từ Gemini AI)",
    "nonce": "Base64(12-byte nonce phản hồi)"
  }
}
```

##### 4. `GET /api/v1/chat/sessions`
- **Mục đích**: Lấy danh sách các phiên chat của người dùng. Trả kèm `session_key_enc_user` và `session_key_nonce_user` để bất kỳ thiết bị mới nào của người dùng cũng có thể giải mã và khôi phục khóa phiên $K_{session}$.
- **Dữ liệu trả về**:
```json
{
  "status_code": 200,
  "message": "Lấy danh sách phiên chat thành công",
  "data": [
    {
      "id": "71f61c99-743c-4490-b694-f18a51acecd0",
      "title_encrypted": "Z3NkZmc...",
      "title_nonce": "MTIzNDU2...",
      "session_key_enc_user": "a2V5X3VzZXI...",
      "session_key_nonce_user": "bm9uY2VfdXNlcg...",
      "created_at": "2026-11-15T15:20:00Z",
      "updated_at": "2026-11-15T15:25:00Z"
    }
  ]
}
```

##### 5. `PATCH /api/v1/chat/sessions/{session_id}`
- **Mục đích**: Cập nhật tiêu đề mã hóa của phiên trò chuyện.
- **Request Body**:
```json
{
  "title_encrypted": "Base64(Ciphertext tiêu đề mới)",
  "title_nonce": "Base64(12-byte nonce tiêu đề mới)"
}
```

##### 6. `GET /api/v1/chat/sessions/{session_id}/messages`
- **Mục đích**: Tải toàn bộ lịch sử tin nhắn mã hóa trong phiên. Client sử dụng $K_{session}$ để giải mã trực tiếp trên trình duyệt hoặc ứng dụng thiết bị đầu cuối.
- **Dữ liệu trả về**:
```json
{
  "status_code": 200,
  "message": "Lấy lịch sử tin nhắn thành công",
  "data": [
    {
      "id": "4b6c3384-...",
      "session_id": "71f61c99-...",
      "role": "user",
      "ciphertext": "...",
      "nonce": "...",
      "created_at": "2026-11-15T15:21:00Z"
    },
    {
      "id": "8a7d2291-...",
      "session_id": "71f61c99-...",
      "role": "model",
      "ciphertext": "...",
      "nonce": "...",
      "created_at": "2026-11-15T15:21:05Z"
    }
  ]
}
```

##### 7. `DELETE /api/v1/chat/sessions/{session_id}`
- **Mục đích**: Xóa vĩnh viễn một phiên trò chuyện cùng toàn bộ tin nhắn liên quan (xóa tầng CASCADE).

---

#### Quản trị viên (Admin Tasks)

##### `POST /api/v1/admin/retrain-model`
- **Mục đích**: Kích hoạt quy trình huấn luyện lại mô hình ML dự báo giao thông trong nền (**BackgroundTasks**). Yêu cầu quyền `role: "admin"`. Tối đa 2 lần/phút.

---

## 7. Luồng nghiệp vụ & Cơ chế xử lý chi tiết (Business Flows)

### Luồng 1: Xác thực JWT & Thu hồi Token tức thì (Token Revocation)

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

### Luồng 6: Trò chuyện AI với Mã hóa E2E & Đồng bộ Đa thiết bị (Dual-Envelope Key Agreement)

```mermaid
sequenceDiagram
    autonumber
    actor ClientA as Device A (User)
    participant API as Chat Endpoint (/chat)
    participant Crypto as Core Crypto Engine
    participant Gemini as GeminiService
    participant DB as Database
    actor ClientB as Device B (User Thiết bị Mới)

    Note over ClientA,API: Bước 1: Khởi tạo khóa & Bắt tay ECDH X25519
    ClientA->>API: GET /api/v1/chat/user-salt
    API-->>ClientA: Trả về {encryption_salt, server_public_key}
    ClientA->>ClientA: Dẫn xuất User Master Key (UMK) từ password + salt (PBKDF2)
    ClientA->>ClientA: Sinh cặp khóa X25519 & tính K_session qua ECDH + HKDF
    ClientA->>ClientA: Mã hóa K_session bằng UMK -> session_key_enc_user
    ClientA->>API: POST /api/v1/chat/handshake (client_pub, session_key_enc_user)
    API->>Crypto: derive_shared_secret(server_priv, client_pub) -> tính K_session
    API->>Crypto: encrypt_server_secret(K_session) -> session_key_enc_server
    API->>DB: Lưu ChatSession (chứa cả 2 bản bọc khóa)
    API-->>ClientA: Trả về {session_id, server_public_key}

    Note over ClientA,Gemini: Bước 2: Gửi câu hỏi bảo mật E2E & Gọi AI
    ClientA->>ClientA: Mã hóa prompt: AES-256-GCM(K_session, {"content": "Tắc đường không?"})
    ClientA->>API: POST /api/v1/chat/message (session_id, ciphertext, nonce)
    API->>DB: Kiểm tra nonce uniqueness (chống replay attack)
    API->>Crypto: decrypt_server_secret() -> Khôi phục K_session trong RAM
    API->>Crypto: decrypt_aes_gcm(K_session, ciphertext, nonce) -> Đọc prompt
    API->>Gemini: generate_response(contents=[prompt + history])
    Gemini-->>API: Trả về câu trả lời: "Đường Láng hiện đang thông thoáng..."
    API->>Crypto: encrypt_aes_gcm(K_session, {"content": ai_reply}) -> (reply_ct, reply_nonce)
    API->>DB: Commit nguyên tử: Lưu user_msg & ai_msg dạng Ciphertext
    API-->>ClientA: Trả về MessageResponse {ciphertext: reply_ct, nonce: reply_nonce}
    ClientA->>ClientA: decrypt_aes_gcm(K_session, reply_ct) -> Hiển thị tin nhắn AI

    Note over ClientB,DB: Bước 3: Thiết bị B đăng nhập & Đồng bộ lịch sử
    ClientB->>API: Đăng nhập -> Nhận JWT & User Salt
    ClientB->>ClientB: Dẫn xuất UMK từ mật khẩu của mình
    ClientB->>API: GET /api/v1/chat/sessions
    API->>DB: Query sessions của user
    API-->>ClientB: Trả về list sessions (kèm session_key_enc_user)
    ClientB->>ClientB: decrypt_aes_gcm(UMK, session_key_enc_user) -> Khôi phục K_session!
    ClientB->>API: GET /api/v1/chat/sessions/{id}/messages
    API->>DB: Query messages (chỉ trả ciphertext + nonce)
    API-->>ClientB: Trả về danh sách messages mã hóa
    ClientB->>ClientB: Dùng K_session giải mã toàn bộ lịch sử trò chuyện cũ thành công!
```

---

## 8. Bảo mật & Giới hạn tần suất (Rate Limiting & Cryptography)

Hệ thống áp dụng kiến trúc phòng thủ chiều sâu (**Defense-in-Depth**), bảo vệ thông tin ở cả tầng truyền tải (In-Transit), tầng xử lý (In-Memory) và tầng lưu trữ (At-Rest):

### 8.1. Ma trận giới hạn tần suất (SlowAPI)

| Endpoint | Giới hạn gọi | Mục đích phòng thủ |
| :--- | :--- | :--- |
| `/api/v1/auth/register` | `5/minute` | Chống spam đăng ký tài khoản tự động |
| `/api/v1/auth/login` | `5/minute` | Chống dò quét mật khẩu (Brute-force) |
| `/api/v1/auth/change-password` | `5/minute` | Bảo vệ tài khoản và chống tấn công đổi mật khẩu hàng loạt |
| `/api/v1/chat/user-salt` | `60/minute` | Đảm bảo hiệu năng cấp salt cho thiết bị |
| `/api/v1/chat/handshake` | `20/minute` | Chống spam bắt tay mã hóa tiêu tốn CPU (X25519) |
| `/api/v1/chat/message` | `30/minute` | Quản lý hạn ngạch gọi Google Gemini API và giải mã AES |
| `/api/v1/chat/sessions` | `60/minute` | Tải danh sách phiên an toàn |
| `/api/v1/chat/sessions/{id}` | `30/minute` (PATCH) / `20/minute` (DELETE) | Cập nhật tiêu đề và xóa phiên |
| `/api/v1/admin/retrain-model` | `2/minute` | Chống quá tải CPU/RAM khi huấn luyện lại mô hình AI |
| `/api/v1/predictions/forecast` | `10/minute` | Tối ưu hóa tài nguyên tính toán inference |
| `/api/v1/directions` | `20/minute` | Tránh nghẽn tính toán Dijkstra liên tục |
| `/api/v1/edges/status` | `60/minute` | Hỗ trợ polling cập nhật bản đồ thời gian thực |

### 8.2. Kiến trúc Mật mã Đầu Cuối (E2E Cryptography) & Zero-Knowledge Storage

1. **Trao đổi khóa ECDH X25519**: Sử dụng chuẩn đường cong Elliptic X25519 (RFC 7748) để thiết lập khóa bí mật chung (`shared_secret`) an toàn mà không cần truyền khóa trực tiếp qua mạng.
2. **Dẫn xuất khóa HKDF & PBKDF2**:
   - `PBKDF2HMAC(SHA256, 100,000 iterations)`: Dẫn xuất `User Master Key` 256-bit từ mật khẩu và `encryption_salt` của người dùng.
   - `HKDF(SHA256)`: Mở rộng `shared_secret` thành khóa đối xứng phiên $K_{session}$ (32 bytes).
3. **Mã hóa xác thực AES-256-GCM**: Toàn bộ payload tin nhắn, tiêu đề và khóa phiên đều được mã hóa bằng AES-256-GCM (Authenticated Encryption with Associated Data).
4. **Chống Replay Attack bằng Nonce Độc Nhất**: Mỗi tin nhắn bắt buộc phải mang một 12-byte random nonce độc nhất. Ràng buộc `UNIQUE(session_id, nonce)` ở cấp database bảo đảm không bao giờ có sự lặp lại nonce trên cùng một khóa phiên.
5. **Nguyên tắc Không Lưu Trữ Dữ Liệu Thô (Zero-Knowledge at Rest)**:
   - Server và Database **hoàn toàn không lưu trữ plaintext** tin nhắn hay mật khẩu/khóa cá nhân của người dùng.
   - Khi cần gọi Google Gemini, server chỉ giải mã prompt tạm thời trong RAM của request hiện tại, gửi đến Gemini qua kênh TLS mã hóa, mã hóa phản hồi ngay khi nhận được, rồi giải phóng plaintext khỏi bộ nhớ.

### 8.3. Các cơ chế bảo mật bổ sung
1. **Mã hóa mật khẩu bằng Argon2**: Sử dụng thuật toán băm mật khẩu tiêu chuẩn hàng đầu thế giới, chống tấn công bằng phần cứng chuyên dụng (GPU/ASIC).
2. **Kiểm tra cấu hình Production bắt buộc**: Khi `ENVIRONMENT != 'dev'`, hệ thống tự động từ chối khởi động nếu `JWT_SECRET_KEY` mang giá trị mặc định hoặc độ dài dưới 32 ký tự.
3. **Che giấu chi tiết lỗi hệ thống**: API `/api/health` và các exception handler không bao giờ để lộ database credentials, internal stack trace hay địa chỉ máy chủ ra ngoài client.

---

## 9. Các Scripts tiện ích (CLI Utilities)

Trong thư mục `scripts/`, dự án cung cấp sẵn 5 công cụ dòng lệnh hoàn chỉnh:

| Script | Mục đích | Hướng dẫn chạy |
| :--- | :--- | :--- |
| `seed_hanoi_network.py` | Nạp dữ liệu các nút giao thông và cung đường mẫu Hà Nội | `uv run python scripts/seed_hanoi_network.py` |
| `generate_synthetic_traffic.py` | Sinh dữ liệu mô phỏng giao thông lớn | `uv run python scripts/generate_synthetic_traffic.py --rows 10000` |
| `import_traffic_csv_to_db.py` | Nhập dữ liệu CSV vào database theo batch 1000 dòng | `uv run python scripts/import_traffic_csv_to_db.py --truncate` |
| `train_prediction_model.py` | Huấn luyện mô hình Random Forest & lưu BLOB vào DB | `uv run python scripts/train_prediction_model.py` |
| `chat_e2e_client_demo.py` | Chạy demo Client E2E: Bắt tay, mã hóa & đồng bộ 2 thiết bị | `uv run python scripts/chat_e2e_client_demo.py` |

> Chi tiết các tham số dòng lệnh và cờ nâng cao xem tại: [scripts/README.md](scripts/README.md).

---

## 10. Kiểm thử tự động (Testing)

Dự án sở hữu bộ kiểm thử tự động toàn diện bao quát tất cả các tầng từ Core Cryptography, Database Models, Services cho đến API Endpoints E2E với **48 bài kiểm thử (100% PASS)**:

```bash
# Chạy toàn bộ 48 bài kiểm thử với pytest qua uv
uv run --with pytest python -m pytest -v
```

### Danh mục các kịch bản kiểm thử:
- `tests/test_admin_retrain_e2e.py`: Kiểm thử luồng E2E gọi API Admin retrain model chạy ngầm qua BackgroundTasks.
- `tests/test_auth_token_revocation.py`: Kiểm thử cơ chế vô hiệu hóa Access Token tức thì khi đổi mật khẩu qua `token_version`.
- `tests/test_chat_api.py`: Kiểm thử toàn bộ API Chatbot E2E (user-salt, handshake, message, sessions, title update, messages history, delete & chống nonce reuse).
- `tests/test_chat_e2e_multidevice.py`: Kiểm thử tích hợp đa thiết bị: Device A tạo chat, Device B đăng nhập từ máy khác và dùng User Master Key khôi phục $K_{session}$ giải mã thành công lịch sử tin nhắn cũ.
- `tests/test_chat_models.py`: Kiểm tra schema `ChatSession`, `ChatMessage`, ràng buộc khóa ngoại CASCADE và unique constraint nonce.
- `tests/test_config_security.py`: Kiểm tra cơ chế tự động từ chối cấu hình insecure JWT secret trên production.
- `tests/test_crypto.py`: Kiểm thử toàn diện thuật toán ECDH X25519, AES-256-GCM, HKDF, PBKDF2 và Server Secret encryption.
- `tests/test_db_models.py`: Kiểm tra schema, ràng buộc khóa ngoại CASCADE và tính toàn vẹn của các thực thể SQLModel.
- `tests/test_gemini_service.py`: Kiểm thử dịch vụ gọi Gemini API: multi-turn context payload, xử lý lỗi thiếu API key và giới hạn quota.
- `tests/test_health_disclosure.py`: Đảm bảo health check không làm rò rỉ thông tin nhạy cảm của hệ thống.
- `tests/test_import_csv.py`: Kiểm thử script import dữ liệu CSV theo batch và truncate table.
- `tests/test_prediction_security.py`: Validate chặt chẽ dữ liệu đầu vào của API dự báo (giới hạn minutes_ahead).
- `tests/test_prediction_service_db.py`: Kiểm thử nạp model từ database và cơ chế heuristic fallback khi DB chưa có model.
- `tests/test_routing_cache.py`: Kiểm thử bộ nhớ đệm đồ thị NetworkX theo TTL.
- `tests/test_security_jwt.py`: Kiểm thử mã hóa và giải mã JWT token roundtrip.
- `tests/test_traffic_service_db.py`: Kiểm tra tính toán snapshot trạng thái giao thông trực tiếp từ bảng `traffic_data`.
- `tests/test_train_prediction_model.py`: Kiểm thử huấn luyện mô hình và lưu BLOB vào `ml_models`.

> Chi tiết về cách chạy từng nhóm kiểm thử xem tại: [tests/README.md](tests/README.md).
