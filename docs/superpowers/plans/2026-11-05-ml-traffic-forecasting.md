# ML Traffic Forecasting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate a Scikit-learn Machine Learning pipeline into the traffic congestion forecasting backend to predict traffic speeds and congestion levels using real-time lag features and time-series patterns, with automatic graceful fallback to the baseline model.

**Architecture:** A feature engineering module (`app/services/features.py`) extracts temporal, road, and real-time lag velocity features from SQLite/PostgreSQL. A training script (`scripts/train_model.py`) trains a Scikit-learn regression model and serializes it to `app/services/ml_model.joblib`. An `MLForecaster` implementing the abstract `Forecaster` interface provides inference with strict staleness and data-sufficiency guards that fallback to `BaselineForecaster` if data is insufficient or stale. The `/api/forecast` and `/api/forecast/map` endpoints are updated with a `model` query parameter.

**Tech Stack:** Python 3.14+, FastAPI, SQLModel, Scikit-learn, Joblib, Pytest.

**Spec:** [`docs/superpowers/specs/2026-11-05-ml-forecasting-design.md`](file:///home/PageNguyen/Projects/TRAFFIC_SYSTEM_BE/docs/superpowers/specs/2026-11-05-ml-forecasting-design.md)

## Global Constraints

- NEVER commit or push (per project forbidden actions).
- NEVER delete files or run destructive terminal commands without asking first.
- NEVER modify anything outside the repository directory (`/home/PageNguyen/Projects/TRAFFIC_SYSTEM_BE`).
- Only add allowed dependencies: `scikit-learn` and `joblib`. Pin exact tested versions in `requirements.txt`.
- Database queries must remain portable across SQLite and PostgreSQL (no dialect-specific SQL functions or upserts).
- Do not store forecast outputs in the database; predictions are computed on demand.
- Keep inference time < 15ms. Fallback gracefully to `baseline-v1` if model artifact is missing or if input data is stale/insufficient; never raise 500 errors.

## Review Focus

1. **Missing Model Artifact**: When `ml_model.joblib` does not exist on disk, requests with `model=ml` must gracefully fallback to `baseline-v1` without throwing an unhandled exception or 500 error.
2. **Stale Traffic Data (> 45 min)**: When the newest observation for a segment is older than 45 minutes relative to `now`, `MLForecaster` must identify the data as stale and fallback to `baseline-v1`.
3. **Insufficient Observations (< 3 observations)**: When fewer than 3 observations exist in the recent $[now - 60m, now]$ window, `MLForecaster` must fallback to `baseline-v1` rather than attempting prediction with missing lag features.
4. **Invalid Model Query Parameter**: When a client requests `GET /api/forecast?model=unknown`, the API must reject the request with HTTP 422 Unprocessable Content.
5. **Output Boundary Clamping**: Predicted speeds from ML regression must never be negative or unrealistically high; they must be clamped within $[5.0, \text{free\_flow\_speed\_kmh} \times 1.1]$.

---

### Task 1: Dependencies Installation & Requirements Pinning

**Files:**
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `scikit-learn` and `joblib` installed in `.venv` and pinned in `requirements.txt`.

- [ ] **Step 1: Install `scikit-learn` and `joblib` into the virtual environment**
  Run: `.venv/bin/uv pip install scikit-learn joblib`
- [ ] **Step 2: Check exact installed versions**
  Run: `.venv/bin/uv pip list | grep -E "^(scikit-learn|joblib) "`
- [ ] **Step 3: Update `requirements.txt` with pinned versions**
  Add the exact versions of `scikit-learn` and `joblib` to `requirements.txt`.
- [ ] **Step 4: Verify imports**
  Run: `.venv/bin/python -c "import sklearn, joblib; print('Dependencies verified:', sklearn.__version__, joblib.__version__)"`
  Expected: Success with versions printed.

---

### Task 2: Feature Extraction Module (`app/services/features.py`)

**Files:**
- Create: `app/services/features.py`
- Test: `tests/test_features.py`

**Interfaces:**
- Consumes: `Segment` from `app.models.segment`, `TrafficObservation` from `app.models.observation`.
- Produces: `extract_features(segment: Segment, target_time: datetime, horizon_minutes: int, recent_observations: list[TrafficObservation]) -> dict[str, Any]` and `FEATURE_COLUMNS: list[str]`.

- [ ] **Step 1: Write failing test in `tests/test_features.py`**
  ```python
  from datetime import datetime
  from app.models.segment import Segment
  from app.models.observation import TrafficObservation
  from app.services.features import extract_features, FEATURE_COLUMNS

  def test_extract_features():
      segment = Segment(
          id=1,
          name="Đường Nguyễn Trãi",
          start_lat=20.99,
          start_lng=105.81,
          end_lat=20.98,
          end_lng=105.79,
          length_m=4200.0,
          road_type="primary",
          free_flow_speed_kmh=60.0,
      )
      obs0 = TrafficObservation(id=1, segment_id=1, timestamp=datetime(2026, 11, 5, 10, 0), avg_speed_kmh=30.0)
      obs1 = TrafficObservation(id=2, segment_id=1, timestamp=datetime(2026, 11, 5, 9, 45), avg_speed_kmh=35.0)
      obs2 = TrafficObservation(id=3, segment_id=1, timestamp=datetime(2026, 11, 5, 9, 30), avg_speed_kmh=40.0)
      target_time = datetime(2026, 11, 5, 10, 30)
      
      feats = extract_features(segment, target_time, 30, [obs0, obs1, obs2])
      assert feats["target_hour"] == 10
      assert feats["target_weekday"] == 3
      assert feats["is_weekend"] == 0
      assert feats["is_rush_hour"] == 0
      assert feats["horizon_minutes"] == 30
      assert feats["free_flow_speed_kmh"] == 60.0
      assert feats["length_m"] == 4200.0
      assert feats["road_type"] == "primary"
      assert feats["lag_speed_0"] == 30.0
      assert feats["lag_speed_1"] == 35.0
      assert feats["lag_speed_2"] == 40.0
      assert feats["speed_trend"] == -5.0
  ```
- [ ] **Step 2: Run test to verify it fails**
  Run: `.venv/bin/pytest tests/test_features.py -q`
  Expected: FAIL with ModuleNotFoundError or ImportError
- [ ] **Step 3: Implement `app/services/features.py`**
  Implement `extract_features` and `FEATURE_COLUMNS` with rush hour defined as 7-9h and 17-19h.
- [ ] **Step 4: Run test to verify it passes**
  Run: `.venv/bin/pytest tests/test_features.py -q`
  Expected: PASS

---

### Task 3: Model Training Script (`scripts/train_model.py`)

**Files:**
- Create: `scripts/train_model.py`

**Interfaces:**
- Consumes: `extract_features` from `app.services.features`, `engine` from `app.core.database`, models `Segment` and `TrafficObservation`.
- Produces: Serialized model file saved to `app/services/ml_model.joblib`.

- [ ] **Step 1: Implement `scripts/train_model.py`**
  - Read segments and observations from database.
  - For each segment, sort observations chronologically.
  - Build training samples $(X, y)$ across horizons 15, 30, 45, 60 minutes.
  - Setup a Scikit-learn Pipeline with `ColumnTransformer` (OneHotEncoder for `road_type`, passthrough/scaler for numeric features) and `HistGradientBoostingRegressor(random_state=42)`.
  - Train the pipeline on collected samples.
  - Save the trained pipeline using `joblib.dump(pipeline, "app/services/ml_model.joblib")`.
- [ ] **Step 2: Run training script on the seeded database**
  Run: `.venv/bin/python scripts/train_model.py`
  Expected: Success output printing dataset size, training metrics (MAE/RMSE), and confirmation that `app/services/ml_model.joblib` was created.
- [ ] **Step 3: Verify model artifact exists and loads**
  Run: `.venv/bin/python -c "import joblib; model = joblib.load('app/services/ml_model.joblib'); print('Model loaded successfully:', type(model))"`
  Expected: Success output.

---

### Task 4: MLForecaster Service (`app/services/ml_forecaster.py`)

**Files:**
- Create: `app/services/ml_forecaster.py`
- Test: `tests/test_ml_forecaster.py`

**Interfaces:**
- Consumes: `Forecaster`, `baseline_forecaster` from `app.services.forecasting`, `extract_features` from `app.services.features`, `calculate_congestion_level` from `app.services.congestion`.
- Produces: `MLForecaster` class and `ml_forecaster` singleton instance with `model_version="ml-v1"`.

- [ ] **Step 1: Write failing tests in `tests/test_ml_forecaster.py`**
  - Test normal ML prediction producing `model_version="ml-v1"`.
  - Test graceful fallback to `baseline-v1` when fewer than 3 observations exist.
  - Test graceful fallback to `baseline-v1` when latest observation is older than 45 minutes.
  - Test graceful fallback when model artifact file is missing or invalid.
  - Test output clamping between 5.0 and `free_flow_speed_kmh * 1.1`.
- [ ] **Step 2: Run test to verify it fails**
  Run: `.venv/bin/pytest tests/test_ml_forecaster.py -q`
  Expected: FAIL with ModuleNotFoundError or ImportError
- [ ] **Step 3: Implement `app/services/ml_forecaster.py`**
  - Implement `MLForecaster(Forecaster)` implementing `forecast(segment, horizon_minutes, session, now)`.
  - Query up to 3 recent observations for the segment in $[now - 60\text{m}, now]$ ordered by timestamp desc.
  - Check guards: if model not loaded, or len(obs) < 3, or $(now - obs_0.timestamp) > 45\text{m}$ -> fallback to `baseline_forecaster.forecast(...)`.
  - Convert extracted feature dictionary to Pandas/NumPy dataframe matching pipeline feature columns.
  - Predict speed, clamp value, calculate congestion level, return `ForecastResponse(..., model_version="ml-v1")`.
- [ ] **Step 4: Run test to verify it passes**
  Run: `.venv/bin/pytest tests/test_ml_forecaster.py -q`
  Expected: PASS

---

### Task 5: API Endpoints Update with `model` Parameter (`app/api/forecast.py`)

**Files:**
- Modify: `app/api/forecast.py`
- Test: `tests/test_forecast.py`

**Interfaces:**
- Consumes: `ml_forecaster` from `app.services.ml_forecaster`, `baseline_forecaster` from `app.services.forecasting`.
- Produces: `GET /api/forecast?segment_id=&horizon=&model=` and `GET /api/forecast/map?horizon=&model=`.

- [ ] **Step 1: Write failing tests in `tests/test_forecast.py`**
  - Test `GET /api/forecast` with `model=ml` returns `model_version="ml-v1"`.
  - Test `GET /api/forecast` with `model=baseline` returns `model_version="baseline-v1"`.
  - Test `GET /api/forecast` with `model=invalid` returns 422 Unprocessable Content.
  - Test `GET /api/forecast/map` with `model=ml` returns list of forecasts with ML.
  - Test `GET /api/forecast/map` with `model=baseline` returns list of forecasts with baseline.
- [ ] **Step 2: Run test to verify it fails**
  Run: `.venv/bin/pytest tests/test_forecast.py -k "model" -q`
  Expected: FAIL
- [ ] **Step 3: Update `app/api/forecast.py`**
  - Add `model: str = Query(default="ml", pattern="^(ml|baseline)$")` to both `get_forecast` and `get_forecast_map`.
  - Select `forecaster = ml_forecaster if model == "ml" else baseline_forecaster`.
- [ ] **Step 4: Run test to verify it passes**
  Run: `.venv/bin/pytest tests/test_forecast.py -q`
  Expected: PASS

---

### Task 6: Comprehensive Verification & Regression Testing

**Files:**
- Modify: `README.md` (add model training command while keeping <= 10 lines)
- Test: All tests in `tests/`

- [ ] **Step 1: Run complete test suite**
  Run: `.venv/bin/pytest -q`
  Expected: All tests pass with 0 warnings/failures.
- [ ] **Step 2: Verify OpenAPI schema includes `model` query parameter**
  Run: `.venv/bin/python -c "from app.main import app; schema = app.openapi(); params = [p['name'] for p in schema['paths']['/api/forecast']['get']['parameters']]; assert 'model' in params; print('OpenAPI verified, params:', params)"`
  Expected: Success output confirming 'model' parameter present.
- [ ] **Step 3: Test fresh database migration, seeding, model training, and API startup**
  Run:
  ```bash
  DATABASE_URL=sqlite:///./e2e_test.db .venv/bin/alembic upgrade head
  DATABASE_URL=sqlite:///./e2e_test.db .venv/bin/python scripts/seed_demo.py
  DATABASE_URL=sqlite:///./e2e_test.db .venv/bin/python scripts/train_model.py
  DATABASE_URL=sqlite:///./e2e_test.db .venv/bin/python -c "from app.main import app; app.openapi()"
  rm -f e2e_test.db
  ```
  Expected: All commands exit with code 0.
