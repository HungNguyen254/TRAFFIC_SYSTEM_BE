# Design: Lưu trữ Dữ liệu Huấn luyện & Mô hình ML vào Database

## 1. Intent & Context
Hiện tại, hệ thống dự báo giao thông đang lưu trữ dữ liệu huấn luyện dạng tệp CSV tĩnh (`data/synthetic_traffic_dataset.csv`) và tệp mô hình đã huấn luyện cục bộ trên đĩa (`app/core/model.joblib`).
Mục tiêu là tái cấu trúc toàn diện để:
- Dữ liệu huấn luyện được quản lý và truy vấn trực tiếp từ bảng cơ sở dữ liệu (`traffic_data`).
- Các mô hình ML sau khi huấn luyện được quản lý phiên bản và lưu nhị phân (BLOB) trực tiếp trong cơ sở dữ liệu (`ml_models`).
- Cung cấp script chuyên dụng để chuyển đổi/nhập (import) dữ liệu từ `.csv` vào database.
- Dịch vụ dự báo (`PredictionService`) tải mô hình đang hoạt động (`is_active=True`) từ cơ sở dữ liệu thay vì đọc từ tệp đĩa.

## 2. Goals & Non-Goals

### Goals
- Tạo model bảng `TrafficData` trong cơ sở dữ liệu để lưu các bản ghi giao thông (đặc trưng huấn luyện và nhãn tốc độ).
- Tạo model bảng `MLModel` trong cơ sở dữ liệu để lưu nhị phân mô hình (`model_bytes`), phiên bản (`version`), chỉ số đánh giá (`metrics`), và cờ trạng thái (`is_active`).
- Viết script `scripts/import_traffic_csv_to_db.py` để nạp dữ liệu từ CSV vào bảng `traffic_data` (hỗ trợ chế độ `--truncate` và `--append`, xử lý theo batch).
- Viết lại `scripts/train_prediction_model.py`: đọc dữ liệu từ `traffic_data`, huấn luyện `RandomForestRegressor`, đánh giá chỉ số, lưu bản ghi mới vào `ml_models` và đánh dấu `is_active=True`.
- Cập nhật `app/services/prediction_service.py` để nạp mô hình từ bảng `ml_models` trong database (bảo toàn cơ chế heuristic fallback khi chưa có mô hình).
- Đảm bảo endpoint admin `POST /admin/retrain-model` tiếp tục hoạt động trơn tru với kiến trúc mới.
- Viết unit tests kiểm thử toàn bộ chu trình: import CSV -> DB, train từ DB -> save ML model vào DB, PredictionService load model từ DB.

### Non-Goals
- Không thay đổi thuật toán dự báo cốt lõi (`RandomForestRegressor`) hoặc định dạng đầu vào/đầu ra của API dự báo.
- Không thay đổi lược đồ các bảng hiện có (`nodes`, `edges`, `predictions`, `users`).

## 3. Detailed Design

### 3.1. Database Schema

#### `TrafficData` (`app/models/traffic_data.py`, table: `traffic_data`)
- `id`: `uuid.UUID` (Primary Key, default uuid4)
- `edge_code`: `str` (Index, max_length=50)
- `street_name`: `str` (max_length=100)
- `length_km`: `float`
- `max_speed_limit`: `int`
- `hour_of_day`: `int`
- `day_of_week`: `int`
- `is_weekend`: `int`
- `is_rush_hour`: `int`
- `weather_code`: `float`
- `average_speed`: `float`
- `congestion_level`: `int`
- `risk_factor`: `float`
- `created_at`: `datetime` (UTC)

#### `MLModel` (`app/models/ml_model.py`, table: `ml_models`)
- `model_id`: `uuid.UUID` (Primary Key, default uuid4)
- `model_name`: `str` (Index, max_length=100, default="traffic_speed_rf")
- `version`: `int` (Tăng dần theo từng lần huấn luyện)
- `model_bytes`: `bytes` (sa.Column(sa.LargeBinary, nullable=False))
- `metrics`: `dict` / `JSON` (ví dụ: `{"r2": float, "samples": int}`)
- `is_active`: `bool` (Index, default=True)
- `created_at`: `datetime` (UTC)

### 3.2. Script Nhập Dữ liệu CSV vào DB (`scripts/import_traffic_csv_to_db.py`)
- Sử dụng module `csv.DictReader` kết hợp batch insert (mỗi lô 1000 bản ghi) vào bảng `TrafficData`.
- Tham số dòng lệnh:
  - `--csv-path`: Đường dẫn file CSV (mặc định: `data/synthetic_traffic_dataset.csv`).
  - `--batch-size`: Số lượng bản ghi mỗi batch (mặc định: 1000).
  - `--truncate`: Làm sạch bảng `traffic_data` trước khi nạp mới.

### 3.3. Script Huấn luyện Mô hình (`scripts/train_prediction_model.py`)
- Mở session kết nối DB (hỗ trợ nhận session truyền vào hoặc tự tạo từ `app.core.database.engine`).
- Nếu bảng `traffic_data` chưa có dữ liệu: tự động gọi hàm import từ `data/synthetic_traffic_dataset.csv` (nếu tồn tại) hoặc sinh mới qua `generate_dataset`.
- Trích xuất ma trận đặc trưng `X` và nhãn `y` từ các bản ghi `TrafficData`.
- Huấn luyện `RandomForestRegressor(n_estimators=40, max_depth=10, random_state=42, n_jobs=-1)`.
- Đánh giá chỉ số: tính R2 score trên tập dữ liệu.
- Serialize mô hình sang nhị phân qua `joblib.dump(model, BytesIO)`.
- Cập nhật DB:
  - Cập nhật các bản ghi cũ của model này thành `is_active = False`.
  - Thêm bản ghi `MLModel` mới với `is_active = True`, `version = max_version + 1`.
  - Commit transaction.

### 3.4. Dịch vụ Dự báo (`app/services/prediction_service.py`)
- `load_model(session: Session | None = None)`:
  - Mở session DB để truy vấn bản ghi `MLModel` có `model_name == "traffic_speed_rf"` và `is_active == True`, sắp xếp theo `version.desc()`.
  - Nếu tìm thấy: giải nén bytes qua `joblib.load(io.BytesIO(record.model_bytes))` và gán vào `cls._model`.
  - Nếu không tìm thấy hoặc xảy ra lỗi: ghi log cảnh báo và fallback về cơ chế heuristic như hiện tại.
- `reload_model()`: Thực hiện `load_model()` trong khối `cls._lock`.

## 4. Verification Plan
1. Chạy script import CSV: `python scripts/import_traffic_csv_to_db.py --truncate` và kiểm tra số bản ghi trong bảng `traffic_data`.
2. Chạy script huấn luyện: `python scripts/train_prediction_model.py` và kiểm tra bản ghi mới trong bảng `ml_models`.
3. Kiểm tra nạp model trong `PredictionService` hoạt động chính xác với model từ database.
4. Chạy toàn bộ test suite hiện có (`pytest`) và viết thêm unit test mới kiểm tra tính năng lưu/nạp model từ DB.
