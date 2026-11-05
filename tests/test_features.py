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

    for col in FEATURE_COLUMNS:
        assert col in feats


def test_extract_features_rush_hour():
    segment = Segment(
        id=1,
        name="Đường Giải Phóng",
        start_lat=20.99,
        start_lng=105.84,
        end_lat=20.96,
        end_lng=105.84,
        length_m=3500.0,
        road_type="primary",
        free_flow_speed_kmh=60.0,
    )
    obs0 = TrafficObservation(id=1, segment_id=1, timestamp=datetime(2026, 11, 5, 7, 30), avg_speed_kmh=20.0)
    obs1 = TrafficObservation(id=2, segment_id=1, timestamp=datetime(2026, 11, 5, 7, 15), avg_speed_kmh=22.0)
    obs2 = TrafficObservation(id=3, segment_id=1, timestamp=datetime(2026, 11, 5, 7, 0), avg_speed_kmh=25.0)
    target_time = datetime(2026, 11, 5, 8, 0)  # 08:00 is morning rush hour

    feats = extract_features(segment, target_time, 30, [obs0, obs1, obs2])
    assert feats["is_rush_hour"] == 1
    assert feats["target_hour"] == 8
