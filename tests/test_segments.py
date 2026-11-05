from datetime import datetime
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models.segment import Segment
from app.models.observation import TrafficObservation


def test_create_and_list_segments(client: TestClient, auth_tokens: dict[str, dict[str, str]]) -> None:
    # 1. Create a segment (requires admin)
    payload = {
        "name": "Đường Giải Phóng",
        "start_lat": 20.9950,
        "start_lng": 105.8420,
        "end_lat": 20.9670,
        "end_lng": 105.8450,
        "length_m": 3500.0,
        "road_type": "primary",
        "free_flow_speed_kmh": 60.0,
    }
    response = client.post("/api/segments", json=payload, headers=auth_tokens["admin"])
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Đường Giải Phóng"
    assert "id" in data
    seg_id = data["id"]

    # 2. List segments (authenticated user or admin)
    list_resp = client.get("/api/segments?limit=10&offset=0", headers=auth_tokens["user"])
    assert list_resp.status_code == 200
    segments = list_resp.json()
    assert len(segments) >= 1
    assert any(s["id"] == seg_id for s in segments)

    # 3. Test pagination validation (le=1000)
    invalid_resp = client.get("/api/segments?limit=1001", headers=auth_tokens["user"])
    assert invalid_resp.status_code == 422


def test_segment_history(client: TestClient, session: Session, auth_tokens: dict[str, dict[str, str]]) -> None:
    # 1. Unknown segment returns 404
    resp_404 = client.get("/api/segments/9999/history", headers=auth_tokens["user"])
    assert resp_404.status_code == 404

    # 2. Create segment and observations
    segment = Segment(
        name="Đường Cầu Giấy",
        start_lat=21.033,
        start_lng=105.798,
        end_lat=21.036,
        end_lng=105.782,
        length_m=2800.0,
        road_type="secondary",
        free_flow_speed_kmh=50.0,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    obs1 = TrafficObservation(
        segment_id=segment.id,  # type: ignore[arg-type]
        timestamp=datetime(2026, 11, 5, 8, 0, 0),
        avg_speed_kmh=25.0,
        vehicle_count=150,
    )
    obs2 = TrafficObservation(
        segment_id=segment.id,  # type: ignore[arg-type]
        timestamp=datetime(2026, 11, 5, 9, 0, 0),
        avg_speed_kmh=35.0,
        vehicle_count=120,
    )
    obs3 = TrafficObservation(
        segment_id=segment.id,  # type: ignore[arg-type]
        timestamp=datetime(2026, 11, 5, 10, 0, 0),
        avg_speed_kmh=45.0,
        vehicle_count=90,
    )
    session.add_all([obs3, obs1, obs2])  # added out of order
    session.commit()

    # 3. History is ordered by timestamp ascending
    resp = client.get(f"/api/segments/{segment.id}/history", headers=auth_tokens["user"])
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) == 3
    assert history[0]["avg_speed_kmh"] == 25.0
    assert history[1]["avg_speed_kmh"] == 35.0
    assert history[2]["avg_speed_kmh"] == 45.0
    # Verify ISO-8601 UTC with 'Z' suffix
    assert history[0]["timestamp"].endswith("Z")

    # 4. History with start and end filters
    filtered_resp = client.get(
        f"/api/segments/{segment.id}/history?start=2026-11-05T08:30:00Z&end=2026-11-05T09:30:00Z",
        headers=auth_tokens["user"],
    )
    assert filtered_resp.status_code == 200
    filtered_history = filtered_resp.json()
    assert len(filtered_history) == 1
    assert filtered_history[0]["avg_speed_kmh"] == 35.0
