# Lưu trữ Dữ liệu Huấn luyện & Mô hình ML vào Database - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuyển đổi toàn bộ quy trình ML: nhập dữ liệu CSV vào bảng database, đọc dữ liệu huấn luyện từ database, lưu trữ artifact model ML dạng binary vào database có đánh số phiên bản, và cập nhật `PredictionService` nạp model trực tiếp từ database.

**Architecture:** Tạo hai bảng SQLModel mới: `TrafficData` (lưu trữ tập dữ liệu giao thông) và `MLModel` (lưu trữ model nhị phân và siêu dữ liệu). Xây dựng script `import_traffic_csv_to_db.py` để nạp CSV theo lô. Tái cấu trúc `train_prediction_model.py` để truy vấn từ `TrafficData` và ghi kết quả vào `MLModel`. Cập nhật `PredictionService` nạp model active từ database với fallback an toàn.

**Tech Stack:** Python 3.14, FastAPI, SQLModel / SQLAlchemy, Scikit-Learn (RandomForestRegressor), Joblib, Pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-db-ml-model-and-training-data-design.md`

## Global Constraints

- Không làm thay đổi cấu trúc bảng cũ: `nodes`, `edges`, `predictions`, `users`.
- Duy trì cơ chế heuristic fallback trong `PredictionService` khi database chưa có mô hình hợp lệ.
- Sử dụng đúng kiểu `sa.LargeBinary` cho trường lưu trữ binary model (`model_bytes`).
- Giữ nguyên luồng endpoint `POST /admin/retrain-model` chạy trong background task.
- Toàn bộ test suite phải vượt qua 100% bằng lệnh `.venv/bin/pytest`.

## Review Focus

1. Bảng `traffic_data` rỗng khi gọi huấn luyện -> Tự động import dữ liệu từ CSV có sẵn hoặc báo lỗi rõ ràng thay vì crash.
2. Binary model trong database bị lỗi/corrupted bytes -> `PredictionService.load_model()` bắt lỗi ngoại lệ, ghi log cảnh báo và fallback về heuristic mà không làm sập ứng dụng.
3. Huấn luyện nhiều lần liên tiếp -> Chỉ có model mới nhất giữ `is_active=True`, các model cũ tự động chuyển thành `is_active=False`, `version` tăng đơn điệu.
4. Tệp CSV chứa dòng không hợp lệ hoặc thiếu cột -> Script import bắt lỗi và bỏ qua dòng hỏng hoặc ném lỗi có thông báo chi tiết.
5. `reload_model()` được gọi đồng thời từ nhiều luồng -> Bảo vệ bằng `threading.Lock` không gây race condition khi gán `cls._model`.

---

### Task 1: Tạo Database Models cho `TrafficData` và `MLModel`

**Files:**
- Create: `app/models/traffic_data.py`
- Create: `app/models/ml_model.py`
- Modify: `app/models/__init__.py:1-1`
- Test: `tests/test_db_models.py`

**Interfaces:**
- Produces:
  - `app.models.traffic_data.TrafficData` (table `traffic_data`)
  - `app.models.ml_model.MLModel` (table `ml_models`)

- [ ] **Step 1: Write the failing test**

Viết file `tests/test_db_models.py` kiểm tra khai báo và khởi tạo bảng `TrafficData` và `MLModel`:

```python
import uuid
from datetime import UTC, datetime
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.ml_model import MLModel
from app.models.traffic_data import TrafficData


def test_traffic_data_model_and_table():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        record = TrafficData(
            edge_code="EDGE_01",
            street_name="Pho Hue",
            length_km=1.2,
            max_speed_limit=50,
            hour_of_day=8,
            day_of_week=1,
            is_weekend=0,
            is_rush_hour=1,
            weather_code=0.0,
            average_speed=22.5,
            congestion_level=2,
            risk_factor=0.55,
        )
        session.add(record)
        session.commit()

        queried = session.exec(select(TrafficData).where(TrafficData.edge_code == "EDGE_01")).first()
        assert queried is not None
        assert queried.average_speed == 22.5
        assert isinstance(queried.id, uuid.UUID)


def test_ml_model_storage_and_query():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        fake_bytes = b"fake-model-binary-data"
        model_entry = MLModel(
            model_name="traffic_speed_rf",
            version=1,
            model_bytes=fake_bytes,
            metrics={"r2": 0.85},
            is_active=True,
        )
        session.add(model_entry)
        session.commit()

        active_model = session.exec(
            select(MLModel).where(MLModel.model_name == "traffic_speed_rf", MLModel.is_active == True)
        ).first()
        assert active_model is not None
        assert active_model.model_bytes == fake_bytes
        assert active_model.version == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_db_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.traffic_data'`

- [ ] **Step 3: Implement `TrafficData`, `MLModel`, and update `app/models/__init__.py`**

1. Tạo `app/models/traffic_data.py`:
```python
import uuid
from datetime import UTC, datetime
import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class TrafficData(SQLModel, table=True):
    __tablename__ = "traffic_data"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(sa.Uuid, primary_key=True, nullable=False),
    )
    edge_code: str = Field(index=True, max_length=50)
    street_name: str = Field(max_length=100)
    length_km: float
    max_speed_limit: int = Field(default=50)
    hour_of_day: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6)
    is_weekend: int = Field(ge=0, le=1)
    is_rush_hour: int = Field(ge=0, le=1)
    weather_code: float = Field(default=0.0)
    average_speed: float
    congestion_level: int = Field(ge=1, le=4)
    risk_factor: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

2. Tạo `app/models/ml_model.py`:
```python
import uuid
from datetime import UTC, datetime
from typing import Any
import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class MLModel(SQLModel, table=True):
    __tablename__ = "ml_models"

    model_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(sa.Uuid, primary_key=True, nullable=False),
    )
    model_name: str = Field(default="traffic_speed_rf", index=True, max_length=100)
    version: int = Field(default=1, index=True)
    model_bytes: bytes = Field(sa_column=sa.Column(sa.LargeBinary, nullable=False))
    metrics: dict[str, Any] | None = Field(default=None, sa_column=sa.Column(sa.JSON, nullable=True))
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

3. Thêm exports vào `app/models/__init__.py`:
```python
from app.models.edge import Edge
from app.models.ml_model import MLModel
from app.models.node import Node
from app.models.prediction import Prediction
from app.models.traffic_data import TrafficData
from app.models.user import User

__all__ = ["Edge", "Node", "Prediction", "User", "TrafficData", "MLModel"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_db_models.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/models/traffic_data.py app/models/ml_model.py app/models/__init__.py tests/test_db_models.py
git commit -m "feat: add TrafficData and MLModel database models"
```

---

### Task 2: Viết Script Chuyển Dữ Liệu CSV vào Database

**Files:**
- Create: `scripts/import_traffic_csv_to_db.py`
- Test: `tests/test_import_csv.py`

**Interfaces:**
- Consumes:
  - `app.models.traffic_data.TrafficData`
  - `app.core.database.engine`
- Produces:
  - `scripts.import_traffic_csv_to_db.import_traffic_csv(csv_path: str | Path, session: Session, batch_size: int = 1000, truncate: bool = False) -> int`

- [ ] **Step 1: Write the failing test**

Tạo file `tests/test_import_csv.py`:

```python
import csv
from pathlib import Path
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.traffic_data import TrafficData
from scripts.import_traffic_csv_to_db import import_traffic_csv


def test_import_traffic_csv_success(tmp_path: Path):
    csv_file = tmp_path / "traffic_sample.csv"
    fieldnames = [
        "edge_code", "street_name", "length_km", "max_speed_limit",
        "hour_of_day", "day_of_week", "is_weekend", "is_rush_hour",
        "weather_code", "average_speed", "congestion_level", "risk_factor"
    ]
    rows = [
        {
            "edge_code": f"EDGE_{i}",
            "street_name": "Nguyen Trai",
            "length_km": "2.5",
            "max_speed_limit": "50",
            "hour_of_day": "8",
            "day_of_week": "2",
            "is_weekend": "0",
            "is_rush_hour": "1",
            "weather_code": "0",
            "average_speed": "25.0",
            "congestion_level": "2",
            "risk_factor": "0.5",
        }
        for i in range(5)
    ]
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        count = import_traffic_csv(csv_path=csv_file, session=session, batch_size=2)
        assert count == 5
        records = session.exec(select(TrafficData)).all()
        assert len(records) == 5

        # Test truncate option
        count2 = import_traffic_csv(csv_path=csv_file, session=session, batch_size=2, truncate=True)
        assert count2 == 5
        records2 = session.exec(select(TrafficData)).all()
        assert len(records2) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_import_csv.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.import_traffic_csv_to_db'`

- [ ] **Step 3: Implement `scripts/import_traffic_csv_to_db.py`**

Viết script hỗ trợ cả gọi trực tiếp từ Python code và chạy CLI:
- Đọc file CSV bằng `csv.DictReader`.
- Nếu `truncate=True`: thực hiện `session.exec(delete(TrafficData))`.
- Parse từng dòng thành đối tượng `TrafficData` và thêm vào batch.
- Commit mỗi khi batch đạt `batch_size`.
- CLI nhận `--csv-path`, `--batch-size`, `--truncate`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_import_csv.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/import_traffic_csv_to_db.py tests/test_import_csv.py
git commit -m "feat: add CSV to database import script"
```

---

### Task 3: Viết lại `scripts/train_prediction_model.py` Đọc Dữ Liệu từ DB và Lưu Model vào DB

**Files:**
- Modify: `scripts/train_prediction_model.py:1-58`
- Test: `tests/test_train_prediction_model.py`

**Interfaces:**
- Consumes:
  - `app.models.traffic_data.TrafficData`
  - `app.models.ml_model.MLModel`
  - `app.core.database.engine`
  - `scripts.import_traffic_csv_to_db.import_traffic_csv`
- Produces:
  - `scripts.train_prediction_model.train_model(session: Session | None = None) -> tuple[RandomForestRegressor, MLModel]`

- [ ] **Step 1: Write the failing test**

Tạo `tests/test_train_prediction_model.py`:

```python
import io
import joblib
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.ml_model import MLModel
from app.models.traffic_data import TrafficData
from scripts.train_prediction_model import train_model


def test_train_model_from_database_and_save_to_db():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Populate minimal records
        for i in range(20):
            session.add(
                TrafficData(
                    edge_code=f"EDGE_{i%4}",
                    street_name="Pho Hue",
                    length_km=1.5,
                    max_speed_limit=50,
                    hour_of_day=i % 24,
                    day_of_week=i % 7,
                    is_weekend=1 if (i % 7) in (5, 6) else 0,
                    is_rush_hour=1 if 7 <= (i % 24) <= 9 else 0,
                    weather_code=0.0,
                    average_speed=30.0 - (i % 10),
                    congestion_level=2,
                    risk_factor=0.4,
                )
            )
        session.commit()

        # Run training
        model, db_model = train_model(session=session)
        assert model is not None
        assert db_model is not None
        assert db_model.is_active is True
        assert db_model.version == 1

        # Check model can be loaded from model_bytes
        loaded_rf = joblib.load(io.BytesIO(db_model.model_bytes))
        assert loaded_rf is not None

        # Train second time: verify version increment and active deactivation
        model2, db_model2 = train_model(session=session)
        assert db_model2.version == 2
        assert db_model2.is_active is True

        old_model = session.exec(select(MLModel).where(MLModel.version == 1)).first()
        assert old_model.is_active is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_train_prediction_model.py -v`
Expected: FAIL because `train_model` signature/behavior still expects CSV and returns only model.

- [ ] **Step 3: Refactor `scripts/train_prediction_model.py`**

Cập nhật `scripts/train_prediction_model.py`:
- Chấp nhận `session: Session | None = None`. Nếu `None`, tự tạo `Session(engine)`.
- Query toàn bộ `TrafficData` từ DB. Nếu chưa có bản ghi, gọi nạp dữ liệu tự động từ CSV/synthetic data trước.
- Build ma trận đặc trưng `X` và mảng nhãn `y` từ `TrafficData`.
- Huấn luyện `RandomForestRegressor`.
- Tính metrics `r2_score`.
- Serialize model sang `io.BytesIO` với `joblib.dump`.
- Tìm `max_version` hiện có trong `MLModel`.
- Chuyển toàn bộ bản ghi `MLModel` cũ của mô hình thành `is_active=False`.
- Lưu bản ghi mới với `version = max_version + 1`, `is_active=True`.
- Commit session và trả về `(model, new_db_model)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_train_prediction_model.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/train_prediction_model.py tests/test_train_prediction_model.py
git commit -m "refactor: train model from DB and persist model artifacts to database"
```

---

### Task 4: Cập nhật `PredictionService` để Nạp Model từ Database

**Files:**
- Modify: `app/services/prediction_service.py:27-52`
- Test: `tests/test_prediction_service_db.py`

**Interfaces:**
- Consumes:
  - `app.models.ml_model.MLModel`
  - `app.core.database.engine`
- Modifies:
  - `app.services.prediction_service.PredictionService.load_model(session: Session | None = None) -> None`
  - `app.services.prediction_service.PredictionService.reload_model() -> None`

- [ ] **Step 1: Write the failing test**

Tạo `tests/test_prediction_service_db.py`:

```python
import io
import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sqlmodel import Session, SQLModel, create_engine

from app.models.ml_model import MLModel
from app.services.prediction_service import PredictionService


def test_prediction_service_loads_active_model_from_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.prediction_service.engine", engine)

    # Train a dummy RF model
    rf = RandomForestRegressor(n_estimators=5, random_state=42)
    X = np.ones((10, 7), dtype=np.float32)
    y = np.ones((10,), dtype=np.float32) * 40.0
    rf.fit(X, y)

    buf = io.BytesIO()
    joblib.dump(rf, buf)
    model_bytes = buf.getvalue()

    with Session(engine) as session:
        entry = MLModel(
            model_name="traffic_speed_rf",
            version=1,
            model_bytes=model_bytes,
            is_active=True,
        )
        session.add(entry)
        session.commit()

        PredictionService.load_model(session=session)
        assert PredictionService._model is not None


def test_prediction_service_fallback_when_no_active_model(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.services.prediction_service.engine", engine)

    with Session(engine) as session:
        PredictionService.load_model(session=session)
        assert PredictionService._model is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_prediction_service_db.py -v`
Expected: FAIL because `load_model` still attempts to read file `MODEL_PATH`.

- [ ] **Step 3: Modify `PredictionService` in `app/services/prediction_service.py`**

- Cập nhật `load_model(cls, session: Session | None = None) -> None`:
  - Lấy session (nếu `session is None`, mở `Session(engine)`).
  - Query:
    ```python
    statement = (
        select(MLModel)
        .where(MLModel.model_name == "traffic_speed_rf", MLModel.is_active == True)
        .order_by(MLModel.version.desc())
    )
    db_model = session.exec(statement).first()
    ```
  - Nếu có `db_model`:
    ```python
    cls._model = joblib.load(io.BytesIO(db_model.model_bytes))
    ```
  - Nếu không có hoặc có exception (corrupt bytes):
    `cls._model = None` và log warning.
- Giữ `reload_model(cls)` thực hiện `load_model()` trong `cls._lock`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_prediction_service_db.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/services/prediction_service.py tests/test_prediction_service_db.py
git commit -m "feat: load active ML model from database in PredictionService"
```

---

### Task 5: Kiểm Thử Toàn Diện và Tích Hợp End-to-End

**Files:**
- Modify: `app/main.py:28-30` (nếu cần tinh chỉnh lifespan)
- Modify: `app/api/v1/endpoints/admin.py:18-25` (đảm bảo _run_retraining hoạt động)
- Test: `tests/test_admin_retrain_e2e.py`

**Interfaces:**
- Verifies:
  - Import CSV -> DB `traffic.db`
  - Train model -> Lưu `traffic.db`
  - Admin endpoint `POST /admin/retrain-model`
  - Toàn bộ suite 16 test cũ + các test mới pass 100%.

- [ ] **Step 1: Write integration test for Admin Retraining & End-to-End flow**

Tạo `tests/test_admin_retrain_e2e.py` kiểm tra `_run_retraining()` thực hiện trọn vẹn: train model -> lưu vào DB -> reload vào `PredictionService`:

```python
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.v1.endpoints.admin import _run_retraining
from app.models.ml_model import MLModel
from app.models.traffic_data import TrafficData
from app.services.prediction_service import PredictionService


def test_admin_retrain_flow(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.core.database.engine", engine)
    monkeypatch.setattr("scripts.train_prediction_model.engine", engine)
    monkeypatch.setattr("app.services.prediction_service.engine", engine)

    # Seed some traffic data
    with Session(engine) as session:
        for i in range(15):
            session.add(
                TrafficData(
                    edge_code="EDGE_TEST",
                    street_name="Test St",
                    length_km=1.0,
                    max_speed_limit=50,
                    hour_of_day=8,
                    day_of_week=0,
                    is_weekend=0,
                    is_rush_hour=1,
                    weather_code=0.0,
                    average_speed=30.0,
                    congestion_level=2,
                    risk_factor=0.4,
                )
            )
        session.commit()

    _run_retraining()

    assert PredictionService._model is not None
    with Session(engine) as session:
        active = session.exec(select(MLModel).where(MLModel.is_active == True)).first()
        assert active is not None
        assert active.version >= 1
```

- [ ] **Step 2: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_admin_retrain_e2e.py -v`
Expected: PASS

- [ ] **Step 3: Import thực tế dữ liệu và chạy train trên database thực tế (`traffic.db`)**

Chạy script import và script train trên cơ sở dữ liệu `traffic.db`:
```bash
.venv/bin/python scripts/import_traffic_csv_to_db.py --truncate
.venv/bin/python scripts/train_prediction_model.py
```
Kiểm tra số lượng bản ghi trong bảng `traffic_data` và `ml_models` trong `traffic.db`.

- [ ] **Step 4: Chạy toàn bộ test suite dự án**

Run: `.venv/bin/pytest -v`
Expected: Tất cả các bài test (cả 16 bài test cũ và các bài test mới) đều PASS 100%.

- [ ] **Step 5: Commit**

```bash
git add app/main.py app/api/v1/endpoints/admin.py tests/test_admin_retrain_e2e.py
git commit -m "feat: complete end-to-end database-backed ML training and model loading"
```
