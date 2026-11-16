import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.database import get_session
from app.main import app
from app.models.edge import Edge
from app.models.traffic_data import TrafficData

EDGE_CODE = "EDGE_HIST_TEST"
EDGE_UID = uuid.UUID("11111111-1111-1111-1111-111111111111")
# 2026-11-09 là thứ 2 -> day_of_week = 0 theo quy ước 0=T2 ... 6=CN của dự án
MONDAY = "2026-11-09"
SUNDAY = "2026-11-08"


def _row(hour: int, dow: int, speed: float, risk: float, rush: int) -> TrafficData:
    return TrafficData(
        edge_code=EDGE_CODE,
        street_name="Tran Duy Hung",
        length_km=3.2,
        max_speed_limit=50,
        hour_of_day=hour,
        day_of_week=dow,
        is_weekend=1 if dow in (5, 6) else 0,
        is_rush_hour=rush,
        weather_code=0.0,
        average_speed=speed,
        congestion_level=1,
        risk_factor=risk,
    )


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Edge(
                edge_id=EDGE_UID,
                edge_code=EDGE_CODE,
                street_name="Tran Duy Hung",
                from_node_id=uuid.uuid4(),
                to_node_id=uuid.uuid4(),
                length_km=3.2,
                max_speed_limit=50,
            )
        )
        session.add_all(
            [
                # Thứ 2, 7h: hai dòng cùng thùng giờ -> phải lấy trung bình
                _row(7, 0, 30.0, 0.2, 1),
                _row(7, 0, 20.0, 0.6, 1),
                # Thứ 2, 8h: một dòng
                _row(8, 0, 40.0, 0.1, 1),
                # 9h thứ 2: không có dòng nào
                # CN 23h: dùng cho test nối sang tuần kế tiếp
                _row(23, 6, 45.0, 0.05, 0),
            ]
        )
        session.commit()
    return engine


@pytest.fixture(name="client")
def client_fixture(engine):
    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    # Không dùng `with`: TestClient không chạy lifespan -> không gọi DB thật
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_history_averages_each_hour_bucket_over_the_range(client):
    response = _get_history(client, EDGE_UID, f"{MONDAY}T07:00:00", f"{MONDAY}T10:00:00")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["edge_id"] == "11111111-1111-1111-1111-111111111111"
    assert data["edge_code"] == EDGE_CODE
    assert data["street_name"] == "Tran Duy Hung"
    assert data["total_hours"] == 3
    assert data["hours_with_data"] == 2

    first, second, third = data["buckets"]
    assert first["time"] == f"{MONDAY}T07:00:00+07:00"
    assert first["hour_of_day"] == 7
    assert first["day_of_week"] == 0
    assert first["is_rush_hour"] == 1
    assert first["average_speed"] == 25.0
    assert first["min_speed"] == 20.0
    assert first["max_speed"] == 30.0
    assert first["risk_factor"] == pytest.approx(0.4)
    assert first["sample_count"] == 2
    # 25 km/h -> mức 2 theo thang của bản đồ, không phải giá trị lưu trong traffic_data (đang là 1)
    assert first["congestion_level"] == 2
    assert first["congestion_text"] == "Di chuyển chậm"

    assert second["average_speed"] == 40.0
    assert second["min_speed"] == 40.0
    assert second["max_speed"] == 40.0
    assert second["sample_count"] == 1
    assert second["congestion_level"] == 1

    assert third["hour_of_day"] == 9
    assert third["average_speed"] is None
    assert third["min_speed"] is None
    assert third["max_speed"] is None
    assert third["risk_factor"] is None
    assert third["sample_count"] == 0


def _get_history(client, edge_uid, start, end):
    return client.get(
        f"/api/v1/edges/{edge_uid}/history", params={"start": start, "end": end}
    )


def test_history_uses_weekday_of_every_hour_across_week_boundary(client):
    response = _get_history(client, EDGE_UID, f"{SUNDAY}T23:00:00", f"{MONDAY}T01:00:00")

    assert response.status_code == 200
    buckets = response.json()["data"]["buckets"]
    assert [b["time"] for b in buckets] == [
        f"{SUNDAY}T23:00:00+07:00",
        f"{MONDAY}T00:00:00+07:00",
    ]
    sunday_hour, monday_hour = buckets
    assert sunday_hour["hour_of_day"] == 23
    assert sunday_hour["day_of_week"] == 6
    assert sunday_hour["average_speed"] == 45.0
    assert monday_hour["day_of_week"] == 0
    assert monday_hour["sample_count"] == 0


def test_history_uses_rush_hour_rule_when_bucket_has_no_rows(client):
    response = _get_history(client, EDGE_UID, f"{MONDAY}T08:00:00", f"{MONDAY}T11:00:00")

    buckets = response.json()["data"]["buckets"]
    # 9h rỗng nhưng vẫn thuộc khung 7-9 cao điểm; 10h rỗng và ngoài khung
    assert [(b["sample_count"], b["is_rush_hour"]) for b in buckets] == [(1, 1), (0, 1), (0, 0)]


def test_history_reports_404_when_edge_does_not_exist(client):
    response = _get_history(
        client, uuid.UUID("99999999-9999-9999-9999-999999999999"), f"{MONDAY}T07:00:00", f"{MONDAY}T08:00:00"
    )

    assert response.status_code == 404
    assert response.json()["error"] == "EDGE_NOT_FOUND"


def test_history_rejects_end_before_start(client):
    response = _get_history(client, EDGE_UID, f"{MONDAY}T08:00:00", f"{MONDAY}T07:00:00")

    assert response.status_code == 400
    assert response.json()["error"] == "EDGE_HISTORY_RANGE_INVALID"


def test_history_rejects_range_wider_than_seven_days(client):
    response = _get_history(client, EDGE_UID, f"{MONDAY}T00:00:00", "2026-11-16T01:00:00")

    assert response.status_code == 400
    assert response.json()["error"] == "EDGE_HISTORY_RANGE_TOO_LARGE"


def test_history_accepts_exactly_seven_days(client):
    response = _get_history(client, EDGE_UID, f"{MONDAY}T00:00:00", "2026-11-16T00:00:00")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_hours"] == 168
    assert len(data["buckets"]) == 168


def test_history_places_naive_and_utc_hours_on_the_local_axis(client):
    response = _get_history(client, EDGE_UID, "2026-11-09T00:00:00Z", "2026-11-09T01:00:00Z")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["granularity"] == "1h"
    assert data["timezone"] == "Asia/Ho_Chi_Minh"
    assert data["data_source"] == "typical_week_profile"
    assert data["start"] == f"{MONDAY}T07:00:00+07:00"
    assert data["end"] == f"{MONDAY}T08:00:00+07:00"
    bucket = data["buckets"][0]
    assert bucket["hour_of_day"] == 7
    assert bucket["average_speed"] == 25.0
