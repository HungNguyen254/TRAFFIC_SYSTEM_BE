# Design Document: Machine Learning Traffic Forecasting

- **Date:** 2026-11-05
- **Status:** Proposed
- **Author:** Antigravity & User

---

## 1. Intent & The Why
Hệ thống hiện tại sử dụng thuật toán cơ sở (`BaselineForecaster` - `baseline-v1`) tính tốc độ dự báo dựa trên trung bình các quan trắc quá khứ trong 8 tuần có cùng `(weekday, hour)`. Mặc dù thuật toán này nắm bắt được tính chu kỳ dài hạn, nó hoàn toàn bỏ qua các diễn biến giao thông tức thời (real-time trends, ví dụ: tắc đường đột xuất, thời tiết xấu, hoặc sự phục hồi tốc độ nhanh chậm trong 15-30 phút vừa qua).
Việc tích hợp mô hình Machine Learning (ML) nhằm kết hợp cả đặc trưng chu kỳ dài hạn lẫn các đặc trưng độ trễ thời gian thực (lag features), nâng cao độ chính xác dự báo tốc độ giao thông và mức độ ùn tắc trên từng đoạn đường.

---

## 2. Goals, Non-Goals, and Anti-Goals

### Goals
- Xây dựng một triển khai `MLForecaster` kế thừa interface trừu tượng `Forecaster`, trả về `ForecastResponse` với `model_version="ml-v1"`.
- Thiết kế module trích xuất đặc trưng (`app/services/features.py`) từ dữ liệu lịch sử và quan trắc gần nhất (lag features).
- Cung cấp script huấn luyện (`scripts/train_model.py`) đọc dữ liệu quan trắc từ database, huấn luyện mô hình hồi quy Scikit-learn và lưu file artifact mô hình (`app/services/ml_model.joblib`).
- Hỗ trợ lựa chọn mô hình qua tham số query `model` trên cả hai endpoint `GET /api/forecast` và `GET /api/forecast/map` (mặc định là `"ml"`, hỗ trợ `"baseline"`).
- Đảm bảo cơ chế tự động phục hồi (graceful fallback): Nếu thiếu dữ liệu gần đây để tính lag hoặc chưa có file model, hệ thống tự động fallback về `BaselineForecaster` (`baseline-v1`) thay vì trả về lỗi 500.
- Viết test suite đầy đủ cho feature extractor, model training/inference, fallback logic và API endpoints.

### Non-Goals
- Không xây dựng pipeline tự động tái huấn luyện theo lịch (không dùng Celery, Cron, APScheduler hay background worker chạy ngầm). Việc huấn luyện được thực thi chủ động thông qua CLI script `python scripts/train_model.py`.
- Không xây dựng mô hình Deep Learning nặng (PyTorch, TensorFlow) hoặc Spatio-Temporal Graph Neural Networks phức tạp vượt quá nhu cầu của hệ thống.
- Không thay đổi cấu trúc bảng cơ sở dữ liệu (`Segment`, `TrafficObservation`). Không tạo bảng lưu trữ kết quả dự báo.

### Anti-Goals
- Tuyệt đối không làm tăng độ trễ endpoint: Inference của mô hình ML phải hoàn thành trong < 15ms.
- Không để xảy ra downtime hoặc lỗi API 500 khi file model chưa được train hoặc dữ liệu quan trắc của một segment bị gián đoạn.

---

## 3. Constraints
- **Môi trường**: Python 3.14+, FastAPI, SQLModel.
- **Dependencies**: Chỉ bổ sung `scikit-learn` và `joblib`, ghim chính xác phiên bản trong `requirements.txt`.
- **Database Portability**: Giữ nguyên nguyên tắc truy vấn portable giữa SQLite và PostgreSQL.
- **Deterministic Testing**: Vẫn duy trì khả năng tiêm đồng hồ `now` trong service và tests.

---

## 4. Approaches Considered

1. **Phương án 1 (Đã chọn): Scikit-learn Regression Pipeline (RandomForest / HistGradientBoosting)**
   - *Mô tả*: Trích xuất đặc trưng thời gian (giờ, thứ, cuối tuần, giờ cao điểm), đặc trưng tuyến đường (tốc độ tự do, chiều dài, loại đường) và đặc trưng độ trễ ngắn hạn (tốc độ tức thời $t_0$, $t_{-1}$, $t_{-2}$, gia tốc tốc độ). Huấn luyện bằng Scikit-learn và lưu artifact `.joblib`.
   - *Ưu điểm*: Độ chính xác cao trên dữ liệu dạng bảng, tốc độ inference cực nhanh (< 5ms), thư viện nhẹ và ổn định.
   - *Lý do chọn*: Đáp ứng chuẩn mực bài toán ML giao thông, tích hợp mượt mà vào interface `Forecaster`.

2. **Phương án 2: Rolling Ridge / Exponential Smoothing trong bộ nhớ**
   - *Mô tả*: Tính toán fitting hồi quy tức thời mỗi khi có request, không lưu file `.joblib`.
   - *Nhược điểm*: Khó nắm bắt các quy luật phi tuyến tính phức tạp (như thay đổi đột ngột giờ cao điểm), tốn CPU trên mỗi request.

3. **Phương án 3: Gradient Boosted Trees nặng (XGBoost / LightGBM)**
   - *Mô tả*: Dùng XGBoost/LightGBM.
   - *Nhược điểm*: Phụ thuộc thư viện C++ ngoài, nặng nề không cần thiết so với quy mô hiện tại.

---

## 5. Detailed Design

### 5.1. Feature Engineering (`app/services/features.py`)
Mỗi mẫu dữ liệu $(X, y)$ bao gồm:
- **Đặc trưng thời gian mục tiêu (Target Time Features)**:
  - `target_hour`: Giờ của thời điểm dự báo ($0 - 23$).
  - `target_weekday`: Thứ trong tuần ($0 - 6$).
  - `is_weekend`: $1$ nếu thứ 7 hoặc Chủ nhật, ngược lại $0$.
  - `is_rush_hour`: $1$ nếu rơi vào 07:00-09:00 hoặc 17:00-19:00, ngược lại $0$.
  - `horizon_minutes`: $15, 30, 45, 60$.
- **Đặc trưng tuyến đường (Segment Features)**:
  - `free_flow_speed_kmh`: Tốc độ thiết kế.
  - `length_m`: Chiều dài đoạn đường.
  - `road_type`: One-hot hoặc target/ordinal encode ("primary", "secondary", "motorway", v.v.).
- **Đặc trưng độ trễ thời gian thực (Real-time Lag Features tại thời điểm `now`)**:
  - `lag_speed_0`: Tốc độ quan trắc mới nhất gần `now` nhất (trong vòng 45 phút).
  - `lag_speed_1`: Tốc độ quan trắc trước đó (khoảng 15 phút trước).
  - `lag_speed_2`: Tốc độ quan trắc trước đó nữa (khoảng 30 phút trước).
  - `speed_trend`: `lag_speed_0 - lag_speed_1` (gia tốc tăng/giảm tốc độ).
- **Target $y$**:
  - `avg_speed_kmh` thực tế tại thời điểm `target_time = now + timedelta(minutes=horizon_minutes)`.

### 5.2. Model Training Script (`scripts/train_model.py`)
- Đọc tất cả các quan trắc từ bảng `TrafficObservation` và thông tin bảng `Segment`.
- Tạo dataset với các cặp thời gian `(now, target_time)` cho các horizon $15, 30, 45, 60$ phút.
- Khởi tạo pipeline Scikit-learn:
  - Tiền xử lý: `ColumnTransformer` (StandardScaler cho số thực, OneHotEncoder cho `road_type`).
  - Regressor: `HistGradientBoostingRegressor` hoặc `RandomForestRegressor(n_estimators=100, random_state=42)`.
- Đánh giá mô hình (MAE, RMSE).
- Lưu mô hình vào `app/services/ml_model.joblib`.

### 5.3. Service Implementation (`app/services/ml_forecaster.py`)
- Class `MLForecaster(Forecaster)`:
  - Nạp mô hình từ `app/services/ml_model.joblib` khi khởi tạo (singleton).
  - Khi gọi `forecast(segment, horizon_minutes, session, now)`:
    1. Kiểm tra nếu file mô hình chưa tồn tại -> gọi `baseline_forecaster.forecast(...)`.
    2. Lấy 3 quan trắc mới nhất của `segment` trong khoảng $[now - 60\text{ minutes}, now]$ sắp xếp theo `timestamp` giảm dần.
    3. Kiểm tra tính hợp lệ & độ mới của dữ liệu (Staleness & Data Sufficiency Guard - *Builder's Call*):
       - Yêu cầu đủ 3 quan trắc gần nhất (`obs_0`, `obs_1`, `obs_2`) trong vòng 60 phút qua. Nếu có ít hơn 3 quan trắc -> fallback gọi `baseline_forecaster.forecast(...)`.
       - Nếu quan trắc mới nhất `obs_0` có độ trễ lớn hơn 45 phút so với `now` -> coi là dữ liệu cũ do gián đoạn truyền tin, fallback gọi `baseline_forecaster.forecast(...)`.
    4. Trích xuất vector đặc trưng $X$ từ 3 quan trắc:
       - `lag_speed_0 = obs_0.avg_speed_kmh`
       - `lag_speed_1 = obs_1.avg_speed_kmh`
       - `lag_speed_2 = obs_2.avg_speed_kmh`
       - `speed_trend = lag_speed_0 - lag_speed_1`
    5. Dự đoán `predicted_speed = float(model.predict(X)[0])`.
    6. Giới hạn giá trị hợp lý: `predicted_speed = max(5.0, min(predicted_speed, segment.free_flow_speed_kmh * 1.1))`.
    7. Tính `congestion_level = calculate_congestion_level(predicted_speed, segment.free_flow_speed_kmh)`.
    8. Trả về `ForecastResponse` với `model_version="ml-v1"`.

### 5.4. API Updates (`app/api/forecast.py`)
- Cập nhật cả hai endpoint:
  - `GET /api/forecast?segment_id=...&horizon=...&model=ml`
  - `GET /api/forecast/map?horizon=...&model=ml`
- Tham số `model: str = Query(default="ml", regex="^(ml|baseline)$")`.
- Nếu `model == "ml"` -> sử dụng `ml_forecaster`.
- Nếu `model == "baseline"` -> sử dụng `baseline_forecaster`.
- Nếu truyền giá trị khác -> FastAPI tự động trả về lỗi 422 Unprocessable Content.

---

## 6. What's Left to the Builder
- Lựa chọn bộ siêu tham số (hyperparameters) cơ bản cho `HistGradientBoostingRegressor` / `RandomForestRegressor` để cân bằng tốc độ huấn luyện và độ chính xác.
- Đảm bảo xử lý ngoại lệ mượt mà trong quá trình nạp file model (ví dụ file bị hỏng hoặc chưa tồn tại thì log warning và fallback tự động).
- Thiết lập kịch bản test suite với mock model hoặc model huấn luyện nhanh trong fixture test.
