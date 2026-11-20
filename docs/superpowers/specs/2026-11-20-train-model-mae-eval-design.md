# Design Document: Huấn luyện mô hình Scikit-learn, Lưu File Model và Đánh giá MAE so với Baseline

## 1. Mục tiêu (Goals)
- Mở rộng script huấn luyện `scripts/train_prediction_model.py` để:
  1. Hỗ trợ chia tập dữ liệu train/test (80/20).
  2. Huấn luyện và đánh giá chỉ số MAE (Mean Absolute Error), RMSE, $R^2$ cho 3 mô hình:
     - Baseline (`DummyRegressor` dự đoán giá trị trung bình)
     - `LinearRegression`
     - `RandomForestRegressor`
  3. Lưu mô hình tốt nhất (`RandomForestRegressor`) ra file tĩnh `models/traffic_model.joblib`.
  4. Tiếp tục lưu bản ghi nhị phân mô hình vào database bảng `ml_models` nhằm giữ nguyên tương thích kiến trúc hệ thống hiện có.
- Cập nhật `.gitignore` để cho phép commit file mô hình trong `models/` nếu cần (`!models/*.joblib` hoặc `!models/traffic_model.joblib`).
- Ghi kết quả so sánh MAE, RMSE, $R^2$ và hướng dẫn chạy vào `README.md`.
- Viết unit tests kiểm thử việc huấn luyện, đánh giá so sánh baseline, lưu file `.joblib` và load lại mô hình.
- Tạo nhánh git, commit, push lên remote và tạo Pull Request (PR) trên GitHub.

## 2. Non-Goals
- Không thay đổi interface của `PredictionService` trong FastAPI (`PredictionService.load_model` vẫn load từ DB `ml_models`).
- Không thêm các thư viện nặng ngoài scikit-learn/joblib/numpy (vốn đã có sẵn trong dự án).

## 3. Kiến trúc & Thiết kế chi tiết

### 3.1. Cấu trúc hàm trong `scripts/train_prediction_model.py`
- `DEFAULT_MODEL_FILE_PATH = Path("models/traffic_model.joblib")`
- `load_training_features_and_target(session: Session | None = None) -> tuple[np.ndarray, np.ndarray]`:
  Truy vấn hoặc nạp dữ liệu giao thông 7 thuộc tính:
  `hour_of_day, day_of_week, is_weekend, is_rush_hour, weather_code, length_km, max_speed_limit`
  và biến mục tiêu: `average_speed`.
- `evaluate_and_compare_models(X: np.ndarray, y: np.ndarray, test_size: float = 0.2, random_state: int = 42) -> dict`:
  Chia train/test split.
  Huấn luyện Baseline (`DummyRegressor(strategy="mean")`), `LinearRegression()`, `RandomForestRegressor(n_estimators=40, max_depth=10, random_state=42, n_jobs=-1)`.
  Tính MAE, RMSE, $R^2$ trên tập test.
- `train_model(session: Session | None = None, model_name: str = DEFAULT_MODEL_NAME, save_file_path: Path | str | None = DEFAULT_MODEL_FILE_PATH) -> tuple[RandomForestRegressor, MLModel, dict]`:
  Gọi các hàm trên, lưu mô hình Random Forest ra đường dẫn file `save_file_path`, lưu vào database bảng `ml_models` kèm theo metrics so sánh, trả về `(rf_model, db_entry, evaluation_results)`.

### 3.2. Cập nhật README.md
Bổ sung mục chi tiết:
- Bảng so sánh kết quả thực nghiệm MAE, RMSE, $R^2$ giữa Baseline vs Linear Regression vs Random Forest.
- Phân tích độ cải thiện: Random Forest giảm ~78.1% sai số MAE so với Baseline, và giảm ~46.7% MAE so với Linear Regression.
- Đường dẫn file mô hình được lưu (`models/traffic_model.joblib`).
- Lệnh chạy huấn luyện và kiểm thử.
