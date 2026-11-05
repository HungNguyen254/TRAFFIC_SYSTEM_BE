from datetime import datetime
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.core.security import create_access_token, hash_password
from app.models.segment import Segment
from app.models.observation import TrafficObservation
from app.models.user import User, UserRole


def setup_users_and_tokens(session: Session):
    admin = User(
        username="admin_user",
        email="admin@crud.test",
        hashed_password=hash_password("adminpass"),
        role=UserRole.ADMIN,
    )
    regular = User(
        username="regular_user",
        email="user@crud.test",
        hashed_password=hash_password("userpass"),
        role=UserRole.USER,
    )
    session.add_all([admin, regular])
    session.commit()
    session.refresh(admin)
    session.refresh(regular)

    admin_token = create_access_token({"sub": str(admin.id), "role": admin.role, "username": admin.username})
    user_token = create_access_token({"sub": str(regular.id), "role": regular.role, "username": regular.username})

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    user_headers = {"Authorization": f"Bearer {user_token}"}

    return admin_headers, user_headers


def test_segments_read_rbac(client: TestClient, session: Session):
    admin_headers, user_headers = setup_users_and_tokens(session)

    # 1. Unauthenticated -> 401
    resp_unauth = client.get("/api/segments")
    assert resp_unauth.status_code == 401

    # 2. Authenticated as regular user -> 200
    resp_user = client.get("/api/segments", headers=user_headers)
    assert resp_user.status_code == 200

    # 3. Authenticated as admin -> 200
    resp_admin = client.get("/api/segments", headers=admin_headers)
    assert resp_admin.status_code == 200


def test_segments_create_rbac(client: TestClient, session: Session):
    admin_headers, user_headers = setup_users_and_tokens(session)

    payload = {
        "name": "Đường Lê Văn Lương",
        "start_lat": 21.005,
        "start_lng": 105.805,
        "end_lat": 20.998,
        "end_lng": 105.792,
        "length_m": 2500.0,
        "road_type": "primary",
        "free_flow_speed_kmh": 60.0,
    }

    # Regular user attempting POST -> 403 Forbidden
    resp_user = client.post("/api/segments", json=payload, headers=user_headers)
    assert resp_user.status_code == 403

    # Admin attempting POST -> 201 Created
    resp_admin = client.post("/api/segments", json=payload, headers=admin_headers)
    assert resp_admin.status_code == 201
    assert resp_admin.json()["name"] == "Đường Lê Văn Lương"


def test_segments_get_by_id(client: TestClient, session: Session):
    admin_headers, user_headers = setup_users_and_tokens(session)

    segment = Segment(
        name="Đường Hoàng Đạo Thúy",
        start_lat=21.01,
        start_lng=105.80,
        end_lat=21.00,
        end_lng=105.81,
        length_m=1800.0,
        road_type="secondary",
        free_flow_speed_kmh=50.0,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    # User can view segment by id -> 200
    resp_user = client.get(f"/api/segments/{segment.id}", headers=user_headers)
    assert resp_user.status_code == 200
    assert resp_user.json()["name"] == "Đường Hoàng Đạo Thúy"

    # Unknown id -> 404
    resp_404 = client.get("/api/segments/99999", headers=user_headers)
    assert resp_404.status_code == 404


def test_segments_update_rbac(client: TestClient, session: Session):
    admin_headers, user_headers = setup_users_and_tokens(session)

    segment = Segment(
        name="Đường Cũ",
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

    update_payload = {
        "name": "Đường Đã Đổi Tên",
        "free_flow_speed_kmh": 65.0,
    }

    # Regular user attempting PUT -> 403 Forbidden
    resp_user = client.put(f"/api/segments/{segment.id}", json=update_payload, headers=user_headers)
    assert resp_user.status_code == 403

    # Admin attempting PUT -> 200
    resp_admin = client.put(f"/api/segments/{segment.id}", json=update_payload, headers=admin_headers)
    assert resp_admin.status_code == 200
    data = resp_admin.json()
    assert data["name"] == "Đường Đã Đổi Tên"
    assert data["free_flow_speed_kmh"] == 65.0
    assert data["length_m"] == 2000.0  # unchanged


def test_segments_delete_rbac(client: TestClient, session: Session):
    admin_headers, user_headers = setup_users_and_tokens(session)

    segment = Segment(
        name="Đường Sắp Bị Xóa",
        start_lat=21.0,
        start_lng=105.8,
        end_lat=21.01,
        end_lng=105.81,
        length_m=1500.0,
        road_type="secondary",
        free_flow_speed_kmh=40.0,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    # Add associated observations
    obs = TrafficObservation(
        segment_id=segment.id,
        timestamp=datetime(2026, 11, 5, 8, 0),
        avg_speed_kmh=30.0,
    )
    session.add(obs)
    session.commit()
    session.refresh(obs)
    obs_id = obs.id

    # Regular user attempting DELETE -> 403 Forbidden
    resp_user = client.delete(f"/api/segments/{segment.id}", headers=user_headers)
    assert resp_user.status_code == 403

    # Admin attempting DELETE -> 200, cascades observations cleanup
    resp_admin = client.delete(f"/api/segments/{segment.id}", headers=admin_headers)
    assert resp_admin.status_code == 200

    # Verify segment and observations deleted
    assert session.get(Segment, segment.id) is None
    assert session.get(TrafficObservation, obs_id) is None


def test_segment_history_requires_auth(client: TestClient, session: Session):
    admin_headers, user_headers = setup_users_and_tokens(session)

    segment = Segment(
        name="Đường History Auth Test",
        start_lat=21.0,
        start_lng=105.8,
        end_lat=21.01,
        end_lng=105.81,
        length_m=1500.0,
        road_type="secondary",
        free_flow_speed_kmh=40.0,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    # Without token -> 401
    resp_no_token = client.get(f"/api/segments/{segment.id}/history")
    assert resp_no_token.status_code == 401

    # With user token -> 200
    resp_user = client.get(f"/api/segments/{segment.id}/history", headers=user_headers)
    assert resp_user.status_code == 200


def test_segments_unauthenticated_mutations(client: TestClient, session: Session):
    segment = Segment(
        name="Đường Unauth Test",
        start_lat=21.0,
        start_lng=105.8,
        end_lat=21.01,
        end_lng=105.81,
        length_m=1000.0,
        road_type="primary",
        free_flow_speed_kmh=50.0,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    # POST without token -> 401
    resp_post = client.post("/api/segments", json={"name": "New"})
    assert resp_post.status_code == 401

    # PUT without token -> 401
    resp_put = client.put(f"/api/segments/{segment.id}", json={"name": "Updated"})
    assert resp_put.status_code == 401

    # DELETE without token -> 401
    resp_del = client.delete(f"/api/segments/{segment.id}")
    assert resp_del.status_code == 401

    # GET /{id} without token -> 401
    resp_get = client.get(f"/api/segments/{segment.id}")
    assert resp_get.status_code == 401

