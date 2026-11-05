from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models.segment import Segment


def test_bulk_observations_ingest_and_idempotency(
    client: TestClient, session: Session
) -> None:
    # 1. Create a segment
    segment = Segment(
        name="Đường Nguyễn Trãi",
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

    seg_id = segment.id

    payload = [
        {
            "segment_id": seg_id,
            "timestamp": "2026-11-05T08:00:00Z",
            "avg_speed_kmh": 30.5,
            "vehicle_count": 210,
        },
        {
            "segment_id": seg_id,
            "timestamp": "2026-11-05T08:15:00Z",
            "avg_speed_kmh": 28.0,
            "vehicle_count": 240,
        },
        {
            "segment_id": seg_id,
            "timestamp": "2026-11-05T08:30:00Z",
            "avg_speed_kmh": 25.0,
            "vehicle_count": 260,
        },
    ]

    # First ingest: all 3 inserted, 0 skipped
    resp1 = client.post("/api/observations", json=payload)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1 == {"inserted": 3, "skipped": 0}

    # Second ingest with same data: 0 inserted, 3 skipped (idempotent)
    resp2 = client.post("/api/observations", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2 == {"inserted": 0, "skipped": 3}

    # Third ingest with mixed new and existing:
    mixed_payload = [
        payload[0],  # already exists
        {
            "segment_id": seg_id,
            "timestamp": "2026-11-05T08:45:00Z",
            "avg_speed_kmh": 22.0,
            "vehicle_count": 270,
        },
    ]
    resp3 = client.post("/api/observations", json=mixed_payload)
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3 == {"inserted": 1, "skipped": 1}


def test_bulk_observations_rejects_unknown_segment(
    client: TestClient, session: Session
) -> None:
    segment = Segment(
        name="Đường Kim Mã",
        start_lat=21.0315,
        start_lng=105.8235,
        end_lat=21.0325,
        end_lng=105.8070,
        length_m=2400.0,
        road_type="secondary",
        free_flow_speed_kmh=50.0,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    # Payload with one valid segment and one invalid segment
    invalid_payload = [
        {
            "segment_id": segment.id,
            "timestamp": "2026-11-05T09:00:00Z",
            "avg_speed_kmh": 35.0,
            "vehicle_count": 100,
        },
        {
            "segment_id": 99999,  # does not exist
            "timestamp": "2026-11-05T09:15:00Z",
            "avg_speed_kmh": 30.0,
            "vehicle_count": 120,
        },
    ]

    # MUST reject the whole request with 422
    resp = client.post("/api/observations", json=invalid_payload)
    assert resp.status_code == 422
