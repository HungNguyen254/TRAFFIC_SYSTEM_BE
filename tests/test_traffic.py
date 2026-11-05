from datetime import datetime
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models.segment import Segment
from app.models.observation import TrafficObservation


def test_get_current_traffic(client: TestClient, session: Session) -> None:
    # 1. Segment with observations
    seg1 = Segment(
        name="Đường Nguyễn Trãi",
        start_lat=20.9984,
        start_lng=105.8130,
        end_lat=20.9856,
        end_lng=105.7958,
        length_m=4200.0,
        road_type="primary",
        free_flow_speed_kmh=60.0,
    )
    # 2. Segment without observations (should be omitted)
    seg2 = Segment(
        name="Đường Chưa Có Dữ Liệu",
        start_lat=21.0000,
        start_lng=105.8000,
        end_lat=21.0100,
        end_lng=105.8100,
        length_m=1000.0,
        road_type="local",
        free_flow_speed_kmh=40.0,
    )
    session.add_all([seg1, seg2])
    session.commit()
    session.refresh(seg1)
    session.refresh(seg2)

    # Add older observation
    obs_old = TrafficObservation(
        segment_id=seg1.id,  # type: ignore[arg-type]
        timestamp=datetime(2026, 11, 5, 8, 0, 0),
        avg_speed_kmh=20.0,
        vehicle_count=200,
    )
    # Add newer observation (latest: 50 km/h out of 60 km/h -> ratio = 0.833 -> "free")
    obs_latest = TrafficObservation(
        segment_id=seg1.id,  # type: ignore[arg-type]
        timestamp=datetime(2026, 11, 5, 9, 0, 0),
        avg_speed_kmh=50.0,
        vehicle_count=100,
    )
    session.add_all([obs_old, obs_latest])
    session.commit()

    resp = client.get("/api/traffic/current")
    assert resp.status_code == 200
    current_data = resp.json()

    # seg2 without observations is omitted
    assert len(current_data) == 1
    item = current_data[0]
    assert item["segment_id"] == seg1.id
    assert item["avg_speed_kmh"] == 50.0
    assert item["congestion_level"] == "free"
    assert item["timestamp"].endswith("Z")
