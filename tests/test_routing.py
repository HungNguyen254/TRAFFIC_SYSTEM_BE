from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.core.database import get_session
from app.core.security import create_access_token
from app.main import app
from app.models.edge import Edge
from app.models.node import Node
from app.models.search_history import SearchHistory
from app.models.user import User


def test_dynamic_routing_and_history_persistence():
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
            email="router_user@example.com",
            password_hash="pw",
            full_name="Router User",
            role="user",
        )
        # Create 3 nodes in Hanoi: A (Ngã tư Sở), B (Hoàng Cầu), C (Cầu Giấy)
        node_a = Node(
            node_code="NODE_A",
            node_name="Ngã tư Sở",
            district="Đống Đa",
            latitude=21.002,
            longitude=105.819,
        )
        node_b = Node(
            node_code="NODE_B",
            node_name="Hoàng Cầu",
            district="Đống Đa",
            latitude=21.018,
            longitude=105.821,
        )
        node_c = Node(
            node_code="NODE_C",
            node_name="Cầu Giấy",
            district="Cầu Giấy",
            latitude=21.033,
            longitude=105.798,
        )
        session.add_all([user, node_a, node_b, node_c])
        session.commit()
        session.refresh(user)
        session.refresh(node_a)
        session.refresh(node_b)
        session.refresh(node_c)

        # Route 1 (Direct via Đường Láng): A -> C directly (4.0 km, speed limit 50)
        edge_direct = Edge(
            edge_code="EDGE_DIRECT",
            street_name="Đường Láng",
            from_node_id=node_a.node_id,
            to_node_id=node_c.node_id,
            length_km=4.0,
            max_speed_limit=50,
        )
        # Route 2 (Alternative via Hoàng Cầu): A -> B (1.5 km), B -> C (2.0 km) = 3.5 km
        edge_sub1 = Edge(
            edge_code="EDGE_SUB1",
            street_name="Tây Sơn - Hoàng Cầu",
            from_node_id=node_a.node_id,
            to_node_id=node_b.node_id,
            length_km=1.5,
            max_speed_limit=50,
        )
        edge_sub2 = Edge(
            edge_code="EDGE_SUB2",
            street_name="Thái Hà - Huỳnh Thúc Kháng - Cầu Giấy",
            from_node_id=node_b.node_id,
            to_node_id=node_c.node_id,
            length_km=2.0,
            max_speed_limit=50,
        )
        session.add_all([edge_direct, edge_sub1, edge_sub2])
        session.commit()

        node_a_id = node_a.node_id
        node_c_id = node_c.node_id
        user_id = user.user_id

        user_token = create_access_token({"sub": str(user.user_id), "role": "user"})

    user_headers = {"Authorization": f"Bearer {user_token}"}

    with TestClient(app) as client:
        # 1. Routing by node IDs with user token
        payload = {
            "origin_id": str(node_a_id),
            "destination_id": str(node_c_id),
            "hour_of_day": 18,
            "weather": "sunny",
        }
        res = client.post("/api/v1/routing/directions", json=payload, headers=user_headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data["nodes"]) >= 2
        assert data["total_distance_km"] > 0
        assert data["estimated_time_minutes"] > 0

        # Verify SearchHistory persisted for authenticated user
        with Session(engine) as session:
            histories = session.exec(select(SearchHistory)).all()
            assert len(histories) == 1
            assert histories[0].user_id == user_id
            assert histories[0].origin_name == "Ngã tư Sở"

        # 2. Routing by natural name as guest (no token)
        payload_guest = {
            "origin_name": "Ngã tư Sở",
            "destination_name": "Cầu Giấy",
            "hour_of_day": 10,
        }
        res_guest = client.post("/api/v1/routing/directions", json=payload_guest)
        assert res_guest.status_code == 200
        assert res_guest.json()["data"]["total_distance_km"] > 0

        # Verify guest SearchHistory persisted with user_id = None
        with Session(engine) as session:
            histories = session.exec(select(SearchHistory)).all()
            assert len(histories) == 2
            assert histories[1].user_id is None

        # 3. Identical origin and destination returns 400
        res_same = client.post(
            "/api/v1/routing/directions",
            json={"origin_id": str(node_a_id), "destination_id": str(node_a_id)},
            headers=user_headers,
        )
        assert res_same.status_code == 400

        # 4. Nonexistent node returns 404
        res_not_found = client.post(
            "/api/v1/routing/directions",
            json={"origin_name": "Địa điểm không tồn tại", "destination_id": str(node_c_id)},
        )
        assert res_not_found.status_code == 404

    app.dependency_overrides.clear()
