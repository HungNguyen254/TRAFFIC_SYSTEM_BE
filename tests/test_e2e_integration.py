from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.database import get_session
from app.core.security import hash_password
from app.main import app
from app.models.user import User
from scripts.seed_hanoi_network import seed_network


def test_full_system_e2e_workflow():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    # 1. Seed complete Hanoi road network
    with Session(engine) as session:
        seed_network(session)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        # 2. Register & Login Regular User
        reg_res = client.post(
            "/api/v1/auth/register",
            json={
                "email": "hanoi_commuter@example.com",
                "password": "Password123!",
                "full_name": "Người Đi Đường Hà Nội",
                "role": "user",
            },
        )
        assert reg_res.status_code == 200

        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "hanoi_commuter@example.com", "password": "Password123!"},
        )
        assert login_res.status_code == 200
        user_token = login_res.json()["data"]["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}

        # 3. Create Admin in database & login
        with Session(engine) as session:
            admin_user = User(
                email="hanoi_admin@example.com",
                password_hash=hash_password("AdminPassword123!"),
                full_name="Quản Trị Hệ Thống Giao Thông",
                role="admin",
            )
            session.add(admin_user)
            session.commit()

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": "hanoi_admin@example.com", "password": "AdminPassword123!"},
        )
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["data"]["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 4. User saves places
        save_place_res = client.post(
            "/api/v1/saved-places",
            json={
                "place_name": "Nhà riêng",
                "address": "Gần Ngã tư Sở, Đống Đa",
                "latitude": 21.0025,
                "longitude": 105.8198,
            },
            headers=user_headers,
        )
        assert save_place_res.status_code == 200

        # 5. User checks traffic forecast for a street at future intervals (30, 60, 120 mins)
        forecast_res = client.post(
            "/api/v1/predictions/forecast",
            json={
                "street_name": "Đường Láng",
                "minutes_ahead": [30, 60, 120],
                "weather": "rain",
            },
        )
        assert forecast_res.status_code == 200
        forecast_data = forecast_res.json()["data"]
        assert len(forecast_data["timeline"]) == 3
        assert forecast_data["timeline"][0]["minutes_ahead"] == 30
        assert forecast_data["timeline"][0]["predicted_speed"] > 0
        assert forecast_data["timeline"][0]["risk_factor"] > 0

        # 6. User searches optimal route avoiding traffic (Ngã tư Sở -> Bờ Hồ)
        route_res = client.post(
            "/api/v1/routing/directions",
            json={
                "origin_name": "Ngã tư Sở",
                "destination_name": "Quảng trường Đông Kinh Nghĩa Thục (Bờ Hồ)",
                "hour_of_day": 18,
                "weather": "rain",
            },
            headers=user_headers,
        )
        assert route_res.status_code == 200
        route_data = route_res.json()["data"]
        assert len(route_data["nodes"]) >= 2
        assert route_data["total_distance_km"] > 0
        assert route_data["estimated_time_minutes"] > 0

        # 7. Check user's trip history
        history_res = client.get("/api/v1/search-histories/me", headers=user_headers)
        assert history_res.status_code == 200
        assert len(history_res.json()["data"]) >= 1

        # 8. User asks AI Chatbot for traffic advice
        chat_res = client.post(
            "/api/v1/chatbot/chat",
            json={"message": "Đường Nguyễn Trãi lúc 18h mưa to có tắc không?", "hour_of_day": 18},
            headers=user_headers,
        )
        assert chat_res.status_code == 200
        assert len(chat_res.json()["data"]["reply"]) > 0

        # 9. Admin updates traffic record on first edge
        edges_res = client.get("/api/v1/edges")
        assert edges_res.status_code == 200
        first_edge_id = edges_res.json()["data"][0]["edge_id"]

        update_traffic_res = client.post(
            "/api/v1/traffic-records/update",
            json={"edge_id": first_edge_id, "current_speed": 12.0},
            headers=admin_headers,
        )
        assert update_traffic_res.status_code == 200
        assert update_traffic_res.json()["data"]["congestion_level"] == 4
        assert update_traffic_res.json()["data"]["color_code"] == "#ef4444"

        # 10. Admin checks system search stats
        admin_stats_res = client.get("/api/v1/search-histories/stats", headers=admin_headers)
        assert admin_stats_res.status_code == 200
        assert admin_stats_res.json()["data"]["total_searches"] >= 1

    app.dependency_overrides.clear()
