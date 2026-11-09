from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.database import get_session
from app.core.security import create_access_token
from app.main import app
from app.models.search_history import SearchHistory
from app.models.user import User


def test_saved_places_and_search_histories():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with Session(engine) as session:
        user = User(
            email="data_user@example.com",
            password_hash="pw",
            full_name="Data User",
            role="user",
        )
        admin = User(
            email="data_admin@example.com",
            password_hash="pw",
            full_name="Data Admin",
            role="admin",
        )
        session.add_all([user, admin])
        session.commit()
        session.refresh(user)
        session.refresh(admin)

        # Seed some search histories
        sh1 = SearchHistory(
            user_id=user.user_id,
            origin_name="Ngã tư Sở",
            origin_lat=21.002,
            origin_lng=105.819,
            destination_name="Cầu Giấy",
            destination_lat=21.033,
            destination_lng=105.798,
        )
        sh2 = SearchHistory(
            user_id=None,
            origin_name="Hoàng Cầu",
            origin_lat=21.018,
            origin_lng=105.821,
            destination_name="Cầu Giấy",
            destination_lat=21.033,
            destination_lng=105.798,
        )
        session.add_all([sh1, sh2])
        session.commit()

        user_token = create_access_token({"sub": str(user.user_id), "role": "user"})
        admin_token = create_access_token({"sub": str(admin.user_id), "role": "admin"})

    user_headers = {"Authorization": f"Bearer {user_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    with TestClient(app) as client:
        # 1. Create Saved Place
        payload = {
            "place_name": "Công ty",
            "address": "Số 1 Trần Duy Hưng",
            "latitude": 21.009,
            "longitude": 105.801,
        }
        res_create = client.post("/api/v1/saved-places", json=payload, headers=user_headers)
        assert res_create.status_code == 200
        saved_id = res_create.json()["data"]["saved_place_id"]

        # 2. List Saved Places
        res_list = client.get("/api/v1/saved-places", headers=user_headers)
        assert res_list.status_code == 200
        assert len(res_list.json()["data"]) == 1
        assert res_list.json()["data"][0]["place_name"] == "Công ty"

        # 3. User gets their own Search History
        res_my_hist = client.get("/api/v1/search-histories/me", headers=user_headers)
        assert res_my_hist.status_code == 200
        assert len(res_my_hist.json()["data"]) == 1
        assert res_my_hist.json()["data"][0]["destination_name"] == "Cầu Giấy"

        # 4. Admin checks search stats
        res_stats = client.get("/api/v1/search-histories/stats", headers=admin_headers)
        assert res_stats.status_code == 200
        stats_data = res_stats.json()["data"]
        assert stats_data["total_searches"] == 2
        assert stats_data["top_destinations"][0]["destination_name"] == "Cầu Giấy"

        # 5. Non-admin forbidden from stats
        res_stats_forbidden = client.get("/api/v1/search-histories/stats", headers=user_headers)
        assert res_stats_forbidden.status_code == 403

        # 6. Delete Saved Place
        res_del = client.delete(f"/api/v1/saved-places/{saved_id}", headers=user_headers)
        assert res_del.status_code == 200

        res_list_after = client.get("/api/v1/saved-places", headers=user_headers)
        assert len(res_list_after.json()["data"]) == 0

    app.dependency_overrides.clear()
