from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.database import get_session
from app.core.security import create_access_token
from app.main import app
from app.models.user import User


def test_traffic_network_crud_and_resolver():
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
        admin = User(
            email="admin_net@example.com",
            password_hash="pw",
            full_name="Admin Net",
            role="admin",
        )
        user = User(
            email="user_net@example.com",
            password_hash="pw",
            full_name="User Net",
            role="user",
        )
        session.add_all([admin, user])
        session.commit()
        session.refresh(admin)
        session.refresh(user)

        admin_token = create_access_token({"sub": str(admin.user_id), "role": "admin"})
        user_token = create_access_token({"sub": str(user.user_id), "role": "user"})

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    user_headers = {"Authorization": f"Bearer {user_token}"}

    with TestClient(app) as client:
        # 1. Non-admin cannot create Node
        node_payload1 = {
            "node_code": "NODE_NTS",
            "node_name": "Ngã tư Sở",
            "district": "Đống Đa",
            "latitude": 21.002,
            "longitude": 105.819,
        }
        res_fail = client.post("/api/v1/nodes", json=node_payload1, headers=user_headers)
        assert res_fail.status_code == 403

        # 2. Admin creates Node 1 & Node 2
        res_node1 = client.post("/api/v1/nodes", json=node_payload1, headers=admin_headers)
        assert res_node1.status_code == 200
        node1_id = res_node1.json()["data"]["node_id"]

        node_payload2 = {
            "node_code": "NODE_CG",
            "node_name": "Nút giao Cầu Giấy",
            "district": "Cầu Giấy",
            "latitude": 21.033,
            "longitude": 105.798,
        }
        res_node2 = client.post("/api/v1/nodes", json=node_payload2, headers=admin_headers)
        assert res_node2.status_code == 200
        node2_id = res_node2.json()["data"]["node_id"]

        # 3. Public GET /nodes
        res_get_nodes = client.get("/api/v1/nodes")
        assert res_get_nodes.status_code == 200
        assert len(res_get_nodes.json()["data"]) == 2

        # 4. Admin creates Edge
        edge_payload = {
            "edge_code": "EDGE_LANG",
            "street_name": "Đường Láng",
            "from_node_id": node1_id,
            "to_node_id": node2_id,
            "length_km": 4.2,
            "max_speed_limit": 50,
        }
        res_edge = client.post("/api/v1/edges", json=edge_payload, headers=admin_headers)
        assert res_edge.status_code == 200
        assert res_edge.json()["data"]["street_name"] == "Đường Láng"

        # 5. Public GET /edges
        res_get_edges = client.get("/api/v1/edges")
        assert res_get_edges.status_code == 200
        assert len(res_get_edges.json()["data"]) == 1

        # 6. Test Node search resolver endpoint
        res_search = client.get("/api/v1/nodes/search?query=sở")
        assert res_search.status_code == 200
        assert len(res_search.json()["data"]) == 1
        assert res_search.json()["data"][0]["node_code"] == "NODE_NTS"

    app.dependency_overrides.clear()
