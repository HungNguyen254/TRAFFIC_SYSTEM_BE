from datetime import datetime, timedelta
from sqlmodel import Session
from app.models.segment import Segment
from app.models.observation import TrafficObservation
from app.services.ml_forecaster import MLForecaster, ml_forecaster


def test_ml_forecaster_normal(session: Session):
    segment = Segment(
        name="Đường Nguyễn Trãi ML",
        start_lat=20.9984,
        start_lng=105.8130,
        end_lat=20.9856,
        end_lng=105.7958,
        length_m=4200.0,
        road_type="primary",
        free_flow_speed_kmh=60.0,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    now = datetime(2026, 11, 5, 10, 0, 0)

    # 3 fresh observations within the last 60 minutes
    obs0 = TrafficObservation(segment_id=segment.id, timestamp=now - timedelta(minutes=5), avg_speed_kmh=35.0)
    obs1 = TrafficObservation(segment_id=segment.id, timestamp=now - timedelta(minutes=20), avg_speed_kmh=38.0)
    obs2 = TrafficObservation(segment_id=segment.id, timestamp=now - timedelta(minutes=35), avg_speed_kmh=42.0)
    session.add_all([obs0, obs1, obs2])
    session.commit()

    resp = ml_forecaster.forecast(segment=segment, horizon_minutes=30, session=session, now=now)
    assert resp.segment_id == segment.id
    assert resp.model_version == "ml-v1"
    assert resp.predicted_speed_kmh > 0
    assert resp.target_time == now + timedelta(minutes=30)
    assert resp.congestion_level in {"free", "busy", "heavy", "jam"}


def test_ml_forecaster_fallback_insufficient_observations(session: Session):
    segment = Segment(
        name="Đường Ít Quan Trắc",
        start_lat=21.0,
        start_lng=105.8,
        end_lat=21.01,
        end_lng=105.81,
        length_m=2000.0,
        road_type="secondary",
        free_flow_speed_kmh=50.0,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    now = datetime(2026, 11, 5, 10, 0, 0)

    # Only 1 observation within last 60 minutes (< 3)
    obs0 = TrafficObservation(segment_id=segment.id, timestamp=now - timedelta(minutes=10), avg_speed_kmh=40.0)
    session.add(obs0)
    session.commit()

    resp = ml_forecaster.forecast(segment=segment, horizon_minutes=15, session=session, now=now)
    # Should fallback gracefully to baseline-v1 without crashing
    assert resp.model_version == "baseline-v1"


def test_ml_forecaster_fallback_stale_data(session: Session):
    segment = Segment(
        name="Đường Dữ Liệu Cũ",
        start_lat=21.0,
        start_lng=105.8,
        end_lat=21.01,
        end_lng=105.81,
        length_m=2000.0,
        road_type="secondary",
        free_flow_speed_kmh=50.0,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    now = datetime(2026, 11, 5, 10, 0, 0)

    # Observations exist, but the newest is 50 minutes old (> 45 min staleness cutoff)
    obs0 = TrafficObservation(segment_id=segment.id, timestamp=now - timedelta(minutes=50), avg_speed_kmh=30.0)
    obs1 = TrafficObservation(segment_id=segment.id, timestamp=now - timedelta(minutes=65), avg_speed_kmh=32.0)
    obs2 = TrafficObservation(segment_id=segment.id, timestamp=now - timedelta(minutes=80), avg_speed_kmh=35.0)
    session.add_all([obs0, obs1, obs2])
    session.commit()

    resp = ml_forecaster.forecast(segment=segment, horizon_minutes=30, session=session, now=now)
    # Must fallback to baseline-v1 due to stale data
    assert resp.model_version == "baseline-v1"


def test_ml_forecaster_fallback_missing_model_file(session: Session):
    segment = Segment(
        name="Đường Test Missing File",
        start_lat=21.0,
        start_lng=105.8,
        end_lat=21.01,
        end_lng=105.81,
        length_m=2000.0,
        road_type="secondary",
        free_flow_speed_kmh=50.0,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    now = datetime(2026, 11, 5, 10, 0, 0)

    forecaster_without_model = MLForecaster(model_path="/non/existent/path/model.joblib")
    resp = forecaster_without_model.forecast(segment=segment, horizon_minutes=15, session=session, now=now)
    # Must fallback gracefully to baseline-v1 without crashing or 500
    assert resp.model_version == "baseline-v1"


def test_ml_forecaster_output_clamping(session: Session):
    segment = Segment(
        name="Đường Clamping Test",
        start_lat=21.0,
        start_lng=105.8,
        end_lat=21.01,
        end_lng=105.81,
        length_m=2000.0,
        road_type="primary",
        free_flow_speed_kmh=50.0,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    now = datetime(2026, 11, 5, 10, 0, 0)
    obs0 = TrafficObservation(segment_id=segment.id, timestamp=now - timedelta(minutes=5), avg_speed_kmh=30.0)
    obs1 = TrafficObservation(segment_id=segment.id, timestamp=now - timedelta(minutes=20), avg_speed_kmh=35.0)
    obs2 = TrafficObservation(segment_id=segment.id, timestamp=now - timedelta(minutes=35), avg_speed_kmh=40.0)
    session.add_all([obs0, obs1, obs2])
    session.commit()

    forecaster = MLForecaster()

    # Mock model returning negative speed (-15.0) -> must clamp to min 5.0
    class MockLowModel:
        def predict(self, X):
            return [-15.0]

    forecaster._model = MockLowModel()
    resp_low = forecaster.forecast(segment=segment, horizon_minutes=15, session=session, now=now)
    assert resp_low.predicted_speed_kmh == 5.0
    assert resp_low.congestion_level == "jam"

    # Mock model returning speed above 110% of free_flow (100.0 km/h) -> must clamp to max 55.0
    class MockHighModel:
        def predict(self, X):
            return [100.0]

    forecaster._model = MockHighModel()
    resp_high = forecaster.forecast(segment=segment, horizon_minutes=15, session=session, now=now)
    assert resp_high.predicted_speed_kmh == 55.0
    assert resp_high.congestion_level == "free"

