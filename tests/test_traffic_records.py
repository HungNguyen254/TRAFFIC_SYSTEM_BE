from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.database import get_session
from app.core.security import create_access_token
from app.main import app
from app.models.edge import Edge
from app.models.node import Node
from app.models.user import User


def test_traffic_records_lifecycle():
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
            email="admin_rec@example.com",
            password_hash="pw",
            full_name="Admin Record",
            role="admin",
        )
        node1 = Node(
            node_code="NODE_1",
            node_name="Node 1",
            district="District 1",
            latitude=21.0,
            longitude=105.8,
        )
        node2 = Node(
            node_code="NODE_2",
            node_name="Node 2",
            district="District 1",
            latitude=21.01,
            longitude=105.81,
        )
        session.add_all([admin, node1, node2])
        session.commit()
        session.refresh(admin)
        session.refresh(node1)
        session.refresh(node2)

        edge = Edge(
            edge_code="EDGE_TEST",
            street_name="Test Street",
            from_node_id=node1.node_id,
            to_node_id=node2.node_id,
            length_km=2.5,
            max_speed_limit=50,
        )
        session.add(edge)
        session.commit()
        session.refresh(edge)

        admin_token = create_access_token({"sub": str(admin.user_id), "role": "admin"})

    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    with TestClient(app) as client:
        # 1. Update traffic record with severe congestion (speed = 10 km/h)
        payload = {
            "edge_id": str(edge.edge_id),
            "current_speed": 10.0,
        }
        res_update = client.post(
            "/api/v1/traffic-records/update", json=payload, headers=admin_headers
        )
        assert res_update.status_code == 200
        rec_data = res_update.json()["data"]
        assert rec_data["congestion_level"] == 4
        assert rec_data["color_code"] == "#ef4444"

        # 2. Get latest traffic records
        res_latest = client.get("/api/v1/traffic-records/latest")
        assert res_latest.status_code == 200
        assert len(res_latest.json()["data"]) >= 1
        assert res_latest.json()["data"][0]["congestion_level"] == 4

    app.dependency_overrides.clear()
