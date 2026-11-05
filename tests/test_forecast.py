from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.main import app
from app.models.segment import Segment
from app.models.observation import TrafficObservation
from app.api.forecast import get_clock


def test_forecast_baseline_hand_computed(client: TestClient, session: Session) -> None:
    # Fix the clock to Thursday 2026-11-05 10:00:00
    fixed_now = datetime(2026, 11, 5, 10, 0, 0)
    app.dependency_overrides[get_clock] = lambda: fixed_now

    # 1. Create a segment
    segment = Segment(
        name="Đại lộ Thăng Long",
        start_lat=21.0040,
        start_lng=105.7890,
        end_lat=21.0010,
        end_lng=105.7050,
        length_m=8000.0,
        road_type="motorway",
        free_flow_speed_kmh=80.0,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    # For horizon = 60 minutes: target_time = 2026-11-05 11:00:00 (Thursday, hour=11)
    # Add matching observations (Thursday, hour 11, within 8 weeks):
    obs1 = TrafficObservation(
        segment_id=segment.id,  # type: ignore[arg-type]
        timestamp=fixed_now - timedelta(days=7) + timedelta(hours=1, minutes=15),  # 2026-10-29 11:15
        avg_speed_kmh=30.0,
    )
    obs2 = TrafficObservation(
        segment_id=segment.id,  # type: ignore[arg-type]
        timestamp=fixed_now - timedelta(days=14) + timedelta(hours=1, minutes=30),  # 2026-10-22 11:30
        avg_speed_kmh=40.0,
    )
    obs3 = TrafficObservation(
        segment_id=segment.id,  # type: ignore[arg-type]
        timestamp=fixed_now - timedelta(days=21) + timedelta(hours=1, minutes=45),  # 2026-10-15 11:45
        avg_speed_kmh=50.0,
    )

    # Non-matching: different hour (hour 12)
    obs_diff_hour = TrafficObservation(
        segment_id=segment.id,  # type: ignore[arg-type]
        timestamp=fixed_now - timedelta(days=7) + timedelta(hours=2),  # hour 12
        avg_speed_kmh=10.0,
    )
    # Non-matching: different weekday (Friday: 6 days ago)
    obs_diff_day = TrafficObservation(
        segment_id=segment.id,  # type: ignore[arg-type]
        timestamp=fixed_now - timedelta(days=6) + timedelta(hours=1),  # Friday hour 11
        avg_speed_kmh=10.0,
    )
    # Non-matching: older than 8 weeks (60 days ago)
    obs_too_old = TrafficObservation(
        segment_id=segment.id,  # type: ignore[arg-type]
        timestamp=fixed_now - timedelta(days=60) + timedelta(hours=1),
        avg_speed_kmh=10.0,
    )

    session.add_all([obs1, obs2, obs3, obs_diff_hour, obs_diff_day, obs_too_old])
    session.commit()

    # Hand-computed mean = (30.0 + 40.0 + 50.0) / 3 = 40.0
    # Ratio = 40.0 / 80.0 = 0.50 -> congestion_level = "busy"
    resp = client.get(f"/api/forecast?segment_id={segment.id}&horizon=60")
    assert resp.status_code == 200
    data = resp.json()

    assert data["segment_id"] == segment.id
    assert data["predicted_speed_kmh"] == 40.0
    assert data["congestion_level"] == "busy"
    assert data["model_version"] == "baseline-v1"
    assert data["target_time"] == "2026-11-05T11:00:00Z"


def test_forecast_fallback_to_free_flow(client: TestClient, session: Session) -> None:
    fixed_now = datetime(2026, 11, 5, 10, 0, 0)
    app.dependency_overrides[get_clock] = lambda: fixed_now

    # Segment with no observations
    segment = Segment(
        name="Đường Mới Không Lịch Sử",
        start_lat=21.0000,
        start_lng=105.8000,
        end_lat=21.0100,
        end_lng=105.8100,
        length_m=1500.0,
        road_type="primary",
        free_flow_speed_kmh=60.0,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    resp = client.get(f"/api/forecast?segment_id={segment.id}&horizon=30")
    assert resp.status_code == 200
    data = resp.json()

    # Fallback to free_flow_speed_kmh (60.0)
    assert data["predicted_speed_kmh"] == 60.0
    # Ratio = 60.0 / 60.0 = 1.0 -> "free"
    assert data["congestion_level"] == "free"
    assert data["target_time"] == "2026-11-05T10:30:00Z"


def test_forecast_validations_and_map(client: TestClient, session: Session) -> None:
    # 1. Invalid horizon (e.g. 20 is not in {15, 30, 45, 60})
    resp_invalid_horizon = client.get("/api/forecast?segment_id=1&horizon=20")
    assert resp_invalid_horizon.status_code == 422

    # 2. Unknown segment -> 404
    resp_unknown_seg = client.get("/api/forecast?segment_id=9999&horizon=15")
    assert resp_unknown_seg.status_code == 404

    # 3. Forecast map invalid horizon
    resp_map_invalid = client.get("/api/forecast/map?horizon=25")
    assert resp_map_invalid.status_code == 422

    # 4. Forecast map valid horizon
    resp_map_valid = client.get("/api/forecast/map?horizon=45")
    assert resp_map_valid.status_code == 200
    assert isinstance(resp_map_valid.json(), list)


def test_forecast_model_parameter(client: TestClient, session: Session) -> None:
    segment = Segment(
        name="Đường Thử Nghiệm Model Param",
        start_lat=21.0,
        start_lng=105.8,
        end_lat=21.01,
        end_lng=105.81,
        length_m=3000.0,
        road_type="primary",
        free_flow_speed_kmh=60.0,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    fixed_now = datetime(2026, 11, 5, 10, 0, 0)
    app.dependency_overrides[get_clock] = lambda: fixed_now

    # With model=baseline
    resp_baseline = client.get(f"/api/forecast?segment_id={segment.id}&horizon=30&model=baseline")
    assert resp_baseline.status_code == 200
    assert resp_baseline.json()["model_version"] == "baseline-v1"

    # With model=invalid -> 422
    resp_invalid = client.get(f"/api/forecast?segment_id={segment.id}&horizon=30&model=unknown")
    assert resp_invalid.status_code == 422

    # Map with model=baseline
    resp_map_base = client.get("/api/forecast/map?horizon=30&model=baseline")
    assert resp_map_base.status_code == 200
    for item in resp_map_base.json():
        assert item["model_version"] == "baseline-v1"

    # Map with model=invalid -> 422
    resp_map_invalid = client.get("/api/forecast/map?horizon=30&model=invalid_model")
    assert resp_map_invalid.status_code == 422


def test_forecast_api_with_ml_model(client: TestClient, session: Session) -> None:
    segment = Segment(
        name="Đường API ML Model",
        start_lat=21.0,
        start_lng=105.8,
        end_lat=21.01,
        end_lng=105.81,
        length_m=3000.0,
        road_type="primary",
        free_flow_speed_kmh=60.0,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    fixed_now = datetime(2026, 11, 5, 10, 0, 0)
    app.dependency_overrides[get_clock] = lambda: fixed_now

    # Seed 3 fresh observations within the last 60 minutes
    obs0 = TrafficObservation(segment_id=segment.id, timestamp=fixed_now - timedelta(minutes=5), avg_speed_kmh=40.0)
    obs1 = TrafficObservation(segment_id=segment.id, timestamp=fixed_now - timedelta(minutes=20), avg_speed_kmh=42.0)
    obs2 = TrafficObservation(segment_id=segment.id, timestamp=fixed_now - timedelta(minutes=35), avg_speed_kmh=45.0)
    session.add_all([obs0, obs1, obs2])
    session.commit()

    # GET /api/forecast with default model (which is ml)
    resp_default = client.get(f"/api/forecast?segment_id={segment.id}&horizon=30")
    assert resp_default.status_code == 200
    assert resp_default.json()["model_version"] == "ml-v1"

    # GET /api/forecast with explicit model=ml
    resp_ml = client.get(f"/api/forecast?segment_id={segment.id}&horizon=30&model=ml")
    assert resp_ml.status_code == 200
    assert resp_ml.json()["model_version"] == "ml-v1"

    # GET /api/forecast/map with model=ml
    resp_map = client.get("/api/forecast/map?horizon=30&model=ml")
    assert resp_map.status_code == 200
    results = resp_map.json()
    assert len(results) >= 1
    matching = [r for r in results if r["segment_id"] == segment.id]
    assert matching[0]["model_version"] == "ml-v1"


