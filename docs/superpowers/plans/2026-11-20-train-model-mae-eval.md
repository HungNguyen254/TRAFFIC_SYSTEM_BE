# ML Model Training, Model File Persistence & Baseline MAE Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Huấn luyện mô hình Scikit-learn (Linear Regression & Random Forest), đánh giá so sánh MAE với Baseline (DummyRegressor), lưu mô hình ra file `models/traffic_model.joblib`, ghi kết quả vào README.md và tạo Pull Request.

**Architecture:** Mở rộng `scripts/train_prediction_model.py` để chia dữ liệu train/test, huấn luyện Baseline, Linear Regression và Random Forest; tính toán các chỉ số đánh giá (MAE, RMSE, $R^2$); lưu mô hình tốt nhất ra file đĩa `models/traffic_model.joblib` và lưu bản ghi vào database `ml_models`. Cập nhật `README.md` với bảng chỉ số và tạo PR nộp link.

**Tech Stack:** Python 3.14, Scikit-learn 1.9+, Joblib 1.6+, SQLModel/SQLAlchemy, NumPy, Pytest, GitHub CLI (`gh`).

**Spec:** `docs/superpowers/specs/2026-11-20-train-model-mae-eval-design.md`

## Global Constraints
- Sử dụng Scikit-learn và các thư viện đã có trong `pyproject.toml` (scikit-learn, joblib, numpy, sqlmodel).
- Giữ nguyên tính tương thích ngược với `PredictionService.load_model` (lưu mô hình nhị phân vào DB `ml_models`).
- File mô hình được lưu tại `models/traffic_model.joblib` và được phép commit trong git (cập nhật ngoại lệ trong `.gitignore`).

## Review Focus
- Trường hợp dữ liệu DB trống: Tự động seed từ CSV trước khi huấn luyện.
- Định dạng dữ liệu và số lượng thuộc tính đầu vào: Đúng 7 features chuẩn.
- File model joblib được ghi ra đĩa: Có thể nạp lại độc lập bằng `joblib.load` và dự đoán cho kết quả nhất quán.
- Cột chỉ số MAE: Được tính toán trên tập test độc lập (hold-out test set), không tính trên tập train.
- Bảng Markdown trong README: Định dạng rõ ràng, chính xác các con số thực nghiệm.

---

### Task 1: Chuẩn bị Git Branch & Cấu hình `.gitignore` cho file model

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Tạo nhánh git mới `feature/t3c69bc-train-model`**
- [ ] **Step 2: Cập nhật `.gitignore` để không loại trừ `!models/*.joblib`**
- [ ] **Step 3: Commit thay đổi cấu hình**

---

### Task 2: Cập nhật `scripts/train_prediction_model.py` với đánh giá Baseline, Linear Regression, Random Forest và lưu file model

**Files:**
- Modify: `scripts/train_prediction_model.py`
- Test: `tests/test_train_prediction_model.py`

**Interfaces:**
- Produces:
  - `evaluate_and_compare_models(X: np.ndarray, y: np.ndarray, test_size: float = 0.2, random_state: int = 42) -> dict`
  - `train_model(session: Session | None = None, model_name: str = "traffic_speed_rf", save_file_path: Path | str | None = Path("models/traffic_model.joblib")) -> tuple[RandomForestRegressor, MLModel, dict]`

- [ ] **Step 1: Viết test cho việc so sánh MAE với baseline và lưu file mô hình ra đĩa trong `tests/test_train_prediction_model.py`**
- [ ] **Step 2: Chạy test để xác nhận test thất bại trước khi cài đặt**
- [ ] **Step 3: Triển khai hàm `evaluate_and_compare_models` và cập nhật `train_model` trong `scripts/train_prediction_model.py`**
- [ ] **Step 4: Chạy test để xác nhận tất cả test pass**
- [ ] **Step 5: Thực thi script huấn luyện để tạo file `models/traffic_model.joblib` thực tế**
- [ ] **Step 6: Commit code**

---

### Task 3: Cập nhật `README.md` với bảng so sánh MAE và hướng dẫn sử dụng

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Bổ sung mục đánh giá mô hình ML và bảng so sánh MAE với Baseline vào `README.md`**
- [ ] **Step 2: Cập nhật mục lục (Table of Contents) nếu cần thiết**
- [ ] **Step 3: Commit cập nhật tài liệu**

---

### Task 4: Chạy toàn bộ test suite, Push branch và Tạo Pull Request

**Files:**
- All files

- [ ] **Step 1: Chạy toàn bộ test suite dự án bằng uv**
- [ ] **Step 2: Push nhánh `feature/t3c69bc-train-model` lên GitHub**
- [ ] **Step 3: Tạo Pull Request vào `main` bằng `gh pr create`**
- [ ] **Step 4: Kiểm tra và cung cấp link PR cho người dùng**
