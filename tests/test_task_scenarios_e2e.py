"""Test case cho 4 nhóm chức năng của đề tài, mỗi nhóm có 4 loại kịch bản:
đúng dữ liệu / sai dữ liệu / chưa đăng nhập / sai quyền.

Mã TC: A=Auth & RBAC, H=History theo giờ, R=Routing, S=Phân tích tuyến thông minh.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.core.database as database_module
from app.core.database import get_session
from app.core.limiter import limiter
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.edge import Edge
from app.models.node import Node
from app.models.traffic_data import TrafficData
from app.models.user import User
from app.services.routing_service import clear_graph_cache
from app.services.traffic_service import clear_traffic_data_cache

# 2026-11-09 là thứ 2 -> day_of_week = 0 theo quy ước 0=T2 ... 6=CN của dự án
TC = timezone(timedelta(hours=7))
MONDAY = "2026-11-09"
MONDAY_7AM = datetime(2026, 11, 9, 7, 0, tzinfo=TC)
EDGE_UID = uuid.UUID("11111111-1111-1111-1111-111111111111")
STRONG_PASSWORD = "Matkhau123!"


@pytest.fixture(name="engine")
def engine_fixture(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    # edges.py đọc Authorization bằng Session(engine) trực tiếp, không qua get_session
    monkeypatch.setattr(database_module, "engine", engine)
    limiter.enabled = False  # các ca test gọi register/login nhiều lần trong 1 phút
    clear_graph_cache()
    clear_traffic_data_cache()
    with Session(engine) as session:
        origin = Node(
            node_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            node_code="N_TEST_ORIGIN",
            node_name="Ngã test",
            district="Quận Test",
            latitude=21.0,
            longitude=105.8,
        )
        dest = Node(
            node_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            node_code="N_TEST_DEST",
            node_name="Đến test",
            district="Quận Test",
            latitude=21.05,
            longitude=105.82,
        )
        orphan = Node(
            node_id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
            node_code="N_TEST_ORPHAN",
            node_name="Nút cô lập",
            district="Quận Test",
            latitude=21.2,
            longitude=105.9,
        )
        session.add_all([origin, dest, orphan])
        session.add(
            Edge(
                edge_id=EDGE_UID,
                edge_code="E_TEST",
                street_name="Tran Duy Hung",
                from_node_id=origin.node_id,
                to_node_id=dest.node_id,
                length_km=3.2,
                max_speed_limit=50,
            )
        )
        # 7h sáng thứ 2: 2 bản ghi cùng thùng giờ -> lịch sử phải lấy trung bình
        for speed, risk in ((30.0, 0.2), (20.0, 0.6)):
            session.add(
                TrafficData(
                    edge_code="E_TEST",
                    street_name="Tran Duy Hung",
                    length_km=3.2,
                    max_speed_limit=50,
                    hour_of_day=7,
                    day_of_week=0,
                    is_weekend=0,
                    is_rush_hour=1,
                    weather_code=0.0,
                    average_speed=speed,
                    congestion_level=1,
                    risk_factor=risk,
                )
            )
        session.add(
            User(
                user_id=uuid.UUID("55555555-5555-5555-5555-555555555555"),
                email="admin@test.vn",
                password_hash=hash_password(STRONG_PASSWORD),
                full_name="Admin Test",
                role="admin",
            )
        )
        session.commit()
    yield engine
    clear_graph_cache()
    clear_traffic_data_cache()
    limiter.enabled = True


@pytest.fixture(name="client")
def client_fixture(engine):
    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    # Không dùng `with`: TestClient sẽ chạy lifespan và gọi DB thật
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(name="db")
def db_fixture(engine):
    with Session(engine) as session:
        yield session


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": STRONG_PASSWORD,
            "confirm_password": STRONG_PASSWORD,
            "full_name": "User Test",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _login(client, email: str, password: str = STRONG_PASSWORD) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


def _token_for(db: Session, email: str, **changes) -> str:
    """Đăng ký + chỉnh user (role/plan) rồi ký token, không cần đi qua các endpoint khác."""
    from sqlmodel import select

    found = db.exec(select(User).where(User.email == email)).first()
    assert found is not None, f"user {email} chưa tồn tại"
    for field, value in changes.items():
        setattr(found, field, value)
    db.add(found)
    db.commit()
    db.refresh(found)
    return create_access_token(
        {"sub": str(found.user_id), "role": found.role, "token_version": found.token_version}
    )


def _history(client, edge_uid=EDGE_UID, start=f"{MONDAY}T07:00:00", end=f"{MONDAY}T08:00:00"):
    return client.get(f"/api/v1/edges/{edge_uid}/history", params={"start": start, "end": end})


# ---------------------------------------------------------------- A. Auth & RBAC


def test_tc_a01_dang_ky_dung(client):
    """TC-A01: đăng ký dữ liệu hợp lệ -> 200, role user, plan standard."""
    data = _register(client, "a01@test.vn")
    assert data["email"] == "a01@test.vn"
    assert data["role"] == "user"
    assert data["plan"] == "standard"


def test_tc_a02_dang_nhap_dung(client):
    """TC-A02: đăng nhập đúng -> 200 kèm access_token dùng được cho /auth/me."""
    _register(client, "a02@test.vn")
    token = _login(client, "a02@test.vn")
    me = client.get("/api/v1/auth/me", headers=_bearer(token))
    assert me.status_code == 200
    assert me.json()["data"]["email"] == "a02@test.vn"


def test_tc_a03_register_sai_dinh_dang_email(client):
    """TC-A03: email sai định dạng -> 422."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": STRONG_PASSWORD,
            "confirm_password": STRONG_PASSWORD,
            "full_name": "User Test",
        },
    )
    assert response.status_code == 422


def test_tc_a04_register_mat_khau_yeu(client):
    """TC-A04: mật khẩu không đủ mạnh (thiếu hoa/ký tự đặc biệt) -> 422.

    BUG-01 (CHƯA sửa): handler 422 không serialize được ctx của pydantic v2, request rơi
    xuống nhánh ValueError và trả 400 "Dữ liệu đầu vào không hợp lệ hoặc bị trùng!".
    """
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "a04@test.vn",
            "password": "abcdefgh",
            "confirm_password": "abcdefgh",
            "full_name": "User Test",
        },
    )
    if response.status_code != 422:
        pytest.xfail(f"BUG-01: mong 422 nhưng nhận {response.status_code}")


def test_tc_a05_register_xac_nhan_khong_khop(client):
    """TC-A05: confirm_password khác password -> 422 (cùng BUG-01 như TC-A04)."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "a05@test.vn",
            "password": STRONG_PASSWORD,
            "confirm_password": "KhacBit123!",
            "full_name": "User Test",
        },
    )
    if response.status_code != 422:
        pytest.xfail(f"BUG-01: mong 422 nhưng nhận {response.status_code}")


def test_tc_a06_register_email_trung(client):
    """TC-A06: email đã tồn tại -> 400."""
    _register(client, "a06@test.vn")
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "a06@test.vn",
            "password": STRONG_PASSWORD,
            "confirm_password": STRONG_PASSWORD,
            "full_name": "User Test",
        },
    )
    assert response.status_code == 400
    assert "đã được đăng ký" in response.json()["message"]


def test_tc_a07_dang_nhap_sai_mat_khau(client):
    """TC-A07: sai mật khẩu -> 401."""
    _register(client, "a07@test.vn")
    response = client.post("/api/v1/auth/login", json={"email": "a07@test.vn", "password": "Sai1234!"})
    assert response.status_code == 401


def test_tc_a08_dang_nhap_email_khong_ton_tai(client):
    """TC-A08: email chưa đăng ký -> 401 (không lộ thông tin tài khoản)."""
    response = client.post(
        "/api/v1/auth/login", json={"email": "khongco@test.vn", "password": STRONG_PASSWORD}
    )
    assert response.status_code == 401


def test_tc_a09_me_khong_token(client):
    """TC-A09: chưa đăng nhập mà gọi /auth/me -> 401."""
    assert client.get("/api/v1/auth/me").status_code == 401


def test_tc_a10_me_token_khong_hop_le(client):
    """TC-A10: token rác / sai ký -> 401."""
    assert client.get("/api/v1/auth/me", headers=_bearer("abc.def.ghi")).status_code == 401


def test_tc_a11_me_token_het_han(client):
    """TC-A11: token hết hạn -> 401."""
    user_id = uuid.UUID("55555555-5555-5555-5555-555555555555")
    expired = create_access_token(
        {"sub": str(user_id), "role": "admin", "token_version": 1},
        expires_delta=timedelta(minutes=-5),
    )
    assert client.get("/api/v1/auth/me", headers=_bearer(expired)).status_code == 401


def test_tc_a12_upgrade_plan_dung(client):
    """TC-A12: user đăng nhập nâng cấp -> 200, plan premium."""
    _register(client, "a12@test.vn")
    token = _login(client, "a12@test.vn")
    response = client.post("/api/v1/auth/upgrade-plan", headers=_bearer(token))
    assert response.status_code == 200
    assert response.json()["data"]["plan"] == "premium"


def test_tc_a13_huy_premium_dung(client):
    """TC-A13: user premium hủy gói -> 200, quay về standard."""
    _register(client, "a13@test.vn")
    token = _login(client, "a13@test.vn")
    client.post("/api/v1/auth/upgrade-plan", headers=_bearer(token))
    response = client.post("/api/v1/auth/cancel-premium", headers=_bearer(token))
    assert response.status_code == 200
    assert response.json()["data"]["plan"] == "standard"


def test_tc_a14_upgrade_khong_dang_nhap(client):
    """TC-A14: chưa đăng nhập mà nâng cấp -> 401."""
    assert client.post("/api/v1/auth/upgrade-plan").status_code == 401


def test_tc_a15_doi_mat_khau_sai_mat_khau_hien_tai(client):
    """TC-A15: current_password sai -> 400, mật khẩu cũ vẫn dùng được."""
    _register(client, "a15@test.vn")
    token = _login(client, "a15@test.vn")
    response = client.post(
        "/api/v1/auth/change-password",
        headers=_bearer(token),
        json={"current_password": "Sai1234!", "new_password": "Moi12345!"},
    )
    assert response.status_code == 400
    assert _login(client, "a15@test.vn") != ""


def test_tc_a16_doi_mat_khau_dung(client):
    """TC-A16: đổi mật khẩu đúng -> 200, mật khẩu cũ bị vô hiệu hóa."""
    _register(client, "a16@test.vn")
    token = _login(client, "a16@test.vn")
    response = client.post(
        "/api/v1/auth/change-password",
        headers=_bearer(token),
        json={"current_password": STRONG_PASSWORD, "new_password": "Moi12345!"},
    )
    assert response.status_code == 200
    assert client.post(
        "/api/v1/auth/login", json={"email": "a16@test.vn", "password": STRONG_PASSWORD}
    ).status_code == 401
    assert client.get("/api/v1/auth/me", headers=_bearer(token)).status_code == 401


def test_tc_a17_admin_endpoint_pha_co_quyen_admin(client, db):
    """TC-A17: user thường gọi API admin -> 403; admin -> không bị 401/403."""
    _register(client, "a17@test.vn")
    user_token = _login(client, "a17@test.vn")
    forbidden = client.get("/api/v1/admin/users", headers=_bearer(user_token))
    assert forbidden.status_code == 403

    admin_token = _token_for(db, "admin@test.vn")
    allowed = client.get("/api/v1/admin/users", headers=_bearer(admin_token))
    assert allowed.status_code == 200, allowed.text


# ---------------------------------------------------------------- H. Lịch sử đoạn đường theo giờ


def test_tc_h01_history_dung_khong_can_dang_nhap(client):
    """TC-H01: khách tra lịch sử đúng khung giờ -> 200, bucket trung bình 2 bản ghi."""
    response = _history(client, start=f"{MONDAY}T07:00:00", end=f"{MONDAY}T09:00:00")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["edge_id"] == str(EDGE_UID)
    assert data["total_hours"] == 2
    first = data["buckets"][0]
    assert first["average_speed"] == 25.0
    assert first["min_speed"] == 20.0
    assert first["max_speed"] == 30.0
    assert first["sample_count"] == 2
    assert first["time"] == f"{MONDAY}T07:00:00+07:00"
    # 8h không có dữ liệu vẫn có bucket trống
    assert data["buckets"][1]["sample_count"] == 0


def test_tc_h02_history_edge_khong_ton_tai(client):
    """TC-H02: edge_id không tồn tại -> 404 EDGE_NOT_FOUND."""
    response = _history(
        client, uuid.UUID("99999999-9999-9999-9999-999999999999"), f"{MONDAY}T07:00:00", f"{MONDAY}T08:00:00"
    )
    assert response.status_code == 404
    assert response.json()["error"] == "EDGE_NOT_FOUND"


def test_tc_h03_history_end_truoc_start(client):
    """TC-H03: end trước start -> 400."""
    response = _history(client, start=f"{MONDAY}T08:00:00", end=f"{MONDAY}T07:00:00")
    assert response.status_code == 400
    assert response.json()["error"] == "EDGE_HISTORY_RANGE_INVALID"


def test_tc_h04_history_qua_7_ngay(client):
    """TC-H04: khoảng thời gian > 7 ngày -> 400."""
    response = _history(client, start=f"{MONDAY}T00:00:00", end="2026-11-16T01:00:00")
    assert response.status_code == 400
    assert response.json()["error"] == "EDGE_HISTORY_RANGE_TOO_LARGE"


def test_tc_h05_history_thoi_gian_sai_dinh_dang(client):
    """TC-H05: start không parse được -> 422."""
    response = _history(client, start="09/11/2026 07:00", end=f"{MONDAY}T08:00:00")
    assert response.status_code == 422


def test_tc_h06_history_edge_id_khong_phai_uuid(client):
    """TC-H06: edge_id không phải UUID -> 422."""
    response = client.get(
        "/api/v1/edges/khong-phai-uuid/history",
        params={"start": f"{MONDAY}T07:00:00", "end": f"{MONDAY}T08:00:00"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------- R. Routing


def test_tc_r01_directions_dung(client):
    """TC-R01: tìm tuyến hợp lệ -> 200, đủ polyline + quãng đường + danh sách đoạn."""
    params = {
        "origin_node_id": "22222222-2222-2222-2222-222222222222",
        "destination_node_id": "33333333-3333-3333-3333-333333333333",
    }
    response = client.get("/api/v1/directions", params=params)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_distance_km"] == 3.2
    assert data["edge_ids"] == [str(EDGE_UID)]
    assert len(data["polyline"]) == 2
    assert len(data["node_ids"]) == 2


def test_tc_r02_directions_khong_dang_nhap_van_public(client):
    """TC-R02: khách chưa đăng nhập vẫn tìm được tuyến -> 200."""
    params = {
        "origin_node_id": "22222222-2222-2222-2222-222222222222",
        "destination_node_id": "33333333-3333-3333-3333-333333333333",
    }
    assert client.get("/api/v1/directions", params=params).status_code == 200


def test_tc_r03_directions_diem_di_trung_diem_den(client):
    """TC-R03: origin == destination -> 400 ROUTE_SAME_ENDPOINT."""
    params = {
        "origin_node_id": "22222222-2222-2222-2222-222222222222",
        "destination_node_id": "22222222-2222-2222-2222-222222222222",
    }
    response = client.get("/api/v1/directions", params=params)
    assert response.status_code == 400
    assert response.json()["error"] == "ROUTE_SAME_ENDPOINT"


def test_tc_r04_directions_node_khong_ton_tai(client):
    """TC-R04: nút giao không có trong đồ thị -> 400 ROUTE_NODE_NOT_FOUND."""
    params = {
        "origin_node_id": "22222222-2222-2222-2222-222222222222",
        "destination_node_id": "99999999-9999-9999-9999-999999999999",
    }
    response = client.get("/api/v1/directions", params=params)
    assert response.status_code == 400
    assert response.json()["error"] == "ROUTE_NODE_NOT_FOUND"


def test_tc_r05_directions_khong_di_duoc(client):
    """TC-R05: nút cô lập không có cạnh nối -> 404 NO_ROUTE_FOUND."""
    params = {
        "origin_node_id": "44444444-4444-4444-4444-444444444444",
        "destination_node_id": "33333333-3333-3333-3333-333333333333",
    }
    response = client.get("/api/v1/directions", params=params)
    assert response.status_code == 404
    assert response.json()["error"] == "NO_ROUTE_FOUND"


def test_tc_r06_directions_thieu_query(client):
    """TC-R06: thiếu origin/destination -> 422."""
    assert client.get("/api/v1/directions").status_code == 422


def test_tc_r07_directions_weight_mode_khong_hop_le(client):
    """TC-R07: weight_mode ngoài enum -> 422."""
    params = {
        "origin_node_id": "22222222-2222-2222-2222-222222222222",
        "destination_node_id": "33333333-3333-3333-3333-333333333333",
        "weight_mode": "fastest",
    }
    assert client.get("/api/v1/directions", params=params).status_code == 422


# ---------------------------------------------------------------- S. Phân tích tuyến thông minh


def _freeze_monday_7am(monkeypatch: pytest.MonkeyPatch) -> None:
    """Giờ "hiện tại" = 7h sáng thứ 2 để trùng đúng khung dữ liệu đã seed."""

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return MONDAY_7AM

    monkeypatch.setattr("app.services.routing_service.datetime", FrozenDatetime)


def _add_parallel_route(db: Session) -> None:
    """Thêm tuyến thứ 2 song song (dài hơn) để có tuyến thay thế khi tuyến chính tắc."""
    origin = db.get(Node, uuid.UUID("22222222-2222-2222-2222-222222222222"))
    dest = db.get(Node, uuid.UUID("33333333-3333-3333-3333-333333333333"))
    mid = Node(
        node_code="N_TEST_MID",
        node_name="Ngã ba test",
        district="Quận Test",
        latitude=21.02,
        longitude=105.9,
    )
    db.add(mid)
    db.commit()
    db.refresh(mid)
    for code, length, speed in (("E_ALT_IN", 8.0, 45.0), ("E_ALT_OUT", 8.0, 45.0)):
        db.add(
            Edge(
                edge_code=code,
                street_name="Nguyen Van Luong",
                from_node_id=origin.node_id if code.endswith("IN") else mid.node_id,
                to_node_id=mid.node_id if code.endswith("IN") else dest.node_id,
                length_km=length,
                max_speed_limit=50,
            )
        )
        db.add(
            TrafficData(
                edge_code=code,
                street_name="Nguyen Van Luong",
                length_km=length,
                max_speed_limit=50,
                hour_of_day=MONDAY_7AM.hour,
                day_of_week=MONDAY_7AM.weekday(),
                is_weekend=0,
                is_rush_hour=1,
                weather_code=0.0,
                average_speed=speed,
                congestion_level=1,
                risk_factor=0.1,
            )
        )
    # Tuyến chính E_TEST tắc 10 km/h tại đúng 7h thứ 2 (đã có 2 bản ghi 30/20 km/h)
    db.add(
        TrafficData(
            edge_code="E_TEST",
            street_name="Tran Duy Hung",
            length_km=3.2,
            max_speed_limit=50,
            hour_of_day=MONDAY_7AM.hour,
            day_of_week=MONDAY_7AM.weekday(),
            is_weekend=0,
            is_rush_hour=1,
            weather_code=0.0,
            average_speed=1.0,
            congestion_level=4,
            risk_factor=0.9,
        )
    )
    db.commit()
    clear_graph_cache()
    clear_traffic_data_cache()


def test_tc_s01_alternatives_co_tuyen_thay_the(client, db, monkeypatch):
    """TC-S01: tuyến chính tắc -> 200, trả thêm tuyến thay thế và so sánh ETA."""
    _freeze_monday_7am(monkeypatch)
    _add_parallel_route(db)
    params = {
        "origin_node_id": "22222222-2222-2222-2222-222222222222",
        "destination_node_id": "33333333-3333-3333-3333-333333333333",
    }
    response = client.get("/api/v1/directions/alternatives", params=params)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["main_route_at_risk"] is True
    assert data["has_alternative"] is True
    assert len(data["options"]) == 2
    main, alt = data["options"]
    assert main["at_risk"] is True
    assert alt["at_risk"] is False
    # Tuyến chính nhanh hơn nhưng nghẽn; tuyến thay thế dài hơn, thông thoáng
    assert main["congestion_level"] > alt["congestion_level"]
    assert main["route"]["total_duration_min"] < alt["route"]["total_duration_min"]


def test_tc_s02_directions_co_flag_nguy_co_tac(client, db, monkeypatch):
    """TC-S02: speed_source=current -> tuyến có risk_segments + risk_warning, ETA theo tốc độ thực."""
    _freeze_monday_7am(monkeypatch)
    _add_parallel_route(db)
    params = {
        "origin_node_id": "22222222-2222-2222-2222-222222222222",
        "destination_node_id": "33333333-3333-3333-3333-333333333333",
        "speed_source": "current",
    }
    response = client.get("/api/v1/directions", params=params)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["risk_segments"], "phải có đoạn nguy cơ tắc"
    assert "nguy cơ tắc cao" in data["risk_warning"]
    assert data["total_duration_min"] > 3.2 / 50 * 60  # ETA lớn hơn tốc độ giới hạn
    assert data["steps"][0]["congestion_level"] == 3  # (30+20+1)/3 = 17 km/h
    assert data["steps"][0]["at_risk"] is True


def test_tc_s03_alternatives_node_khong_ton_tai(client):
    """TC-S03: /alternatives với nút không tồn tại -> 400."""
    params = {
        "origin_node_id": "22222222-2222-2222-2222-222222222222",
        "destination_node_id": "99999999-9999-9999-9999-999999999999",
    }
    response = client.get("/api/v1/directions/alternatives", params=params)
    assert response.status_code == 400
    assert response.json()["error"] == "ROUTE_NODE_NOT_FOUND"


def test_tc_s04_forecast_route_can_premium(client, db):
    """TC-S04: dự báo ETA theo tuyến - user premium -> 200, user thường -> 403."""
    premium_token = _token_for(db, "admin@test.vn", plan="premium")
    payload = {
        "base_time": f"{MONDAY}T07:00:00+07:00",
        "steps": [{"edge_id": str(EDGE_UID), "baseline_travel_min": 5}],
    }
    ok = client.post("/api/v1/predictions/forecast/route", json=payload, headers=_bearer(premium_token))
    assert ok.status_code == 200, ok.text

    _register(client, "s04@test.vn")
    standard_token = _login(client, "s04@test.vn")
    denied = client.post(
        "/api/v1/predictions/forecast/route", json=payload, headers=_bearer(standard_token)
    )
    assert denied.status_code == 403


def test_tc_s05_forecast_route_sai_du_lieu(client, db):
    """TC-S05: dữ liệu dự báo không hợp lệ -> 422 (thiếu steps / phút ngoài khoảng)."""
    premium_token = _token_for(db, "admin@test.vn", plan="premium")
    assert client.post(
        "/api/v1/predictions/forecast/route", json={"base_time": f"{MONDAY}T07:00:00+07:00"}, headers=_bearer(premium_token)
    ).status_code == 422
    assert client.post(
        "/api/v1/predictions/forecast/route",
        json={
            "base_time": f"{MONDAY}T07:00:00+07:00",
            "steps": [{"edge_id": str(EDGE_UID), "baseline_travel_min": -1}],
        },
        headers=_bearer(premium_token),
    ).status_code == 422


def test_tc_s06_forecast_route_khong_dang_nhap(client):
    """TC-S06: chưa đăng nhập gọi API dự báo dành cho Premium -> 401."""
    payload = {
        "base_time": f"{MONDAY}T07:00:00+07:00",
        "steps": [{"edge_id": str(EDGE_UID), "baseline_travel_min": 5}],
    }
    assert client.post("/api/v1/predictions/forecast/route", json=payload).status_code == 401


def test_tc_s07_map_forecast_theo_gio_phan_quyen(client, db):
    """TC-S07: tra cứu bản đồ theo khung giờ (hour) - quyền phải nhất quán.

    Standard -> 403, Premium -> 200. BUG-02 (CHƯA sửa): khách chưa đăng nhập vẫn được 200,
    vì _reject_hour_query_for_standard chỉ chặn khi đã có user và plan != premium.
    """
    premium_token = _token_for(db, "admin@test.vn", plan="premium")
    _register(client, "s07@test.vn")
    standard_token = _login(client, "s07@test.vn")
    params = {"hour": 7, "min_lat": 20.9, "min_lng": 105.5, "max_lat": 21.2, "max_lng": 105.9}

    premium = client.get("/api/v1/edges", params=params, headers=_bearer(premium_token))
    assert premium.status_code == 200, premium.text

    standard = client.get("/api/v1/edges", params=params, headers=_bearer(standard_token))
    assert standard.status_code == 403

    guest = client.get("/api/v1/edges", params=params)
    if guest.status_code != 403:
        pytest.xfail(f"BUG-02: khách tra cứu theo giờ mong 403 nhưng nhận {guest.status_code}")
