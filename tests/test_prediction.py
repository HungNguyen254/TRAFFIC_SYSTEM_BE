import uuid
from datetime import UTC, datetime
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.core.database import get_session
from app.core.security import create_access_token
from app.main import app
from app.models.edge import Edge
from app.models.node import Node
from app.models.prediction import Prediction
from app.models.user import User
from app.schemas.prediction import PredictionRequest, PredictionTimelineItem, PredictionResponse
from app.services.prediction_service import PredictionService


def test_prediction_request_schema_validation():
    # Valid default
    req = PredictionRequest()
    assert req.minutes_ahead == [30, 60, 120]

    # Valid custom
    req_custom = PredictionRequest(minutes_ahead=[15, 45, 90])
    assert req_custom.minutes_ahead == [15, 45, 90]

    # Invalid empty minutes_ahead
    with pytest.raises(ValidationError):
        PredictionRequest(minutes_ahead=[])

    # Invalid negative minute
    with pytest.raises(ValidationError):
        PredictionRequest(minutes_ahead=[-10])

    # Invalid boundary 0 minute
    with pytest.raises(ValidationError):
        PredictionRequest(minutes_ahead=[0])

    # Invalid minute > 1440
    with pytest.raises(ValidationError):
        PredictionRequest(minutes_ahead=[1441])


def test_prediction_service_timeline_calculation():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        node1 = Node(
            node_code="NODE_TL1",
            node_name="Node TL1",
            district="District TL1",
            latitude=21.0,
            longitude=105.8,
        )
        node2 = Node(
            node_code="NODE_TL2",
            node_name="Node TL2",
            district="District TL2",
            latitude=21.01,
            longitude=105.81,
        )
        session.add_all([node1, node2])
        session.commit()
        session.refresh(node1)
        session.refresh(node2)

        edge = Edge(
            edge_code="EDGE_TL",
            street_name="Timeline Avenue",
            from_node_id=node1.node_id,
            to_node_id=node2.node_id,
            length_km=2.5,
            max_speed_limit=60,
        )
        session.add(edge)
        session.commit()
        session.refresh(edge)

        req = PredictionRequest(
            edge_id=edge.edge_id,
            minutes_ahead=[120, 30, 60],
            weather="sunny",
        )
        res = PredictionService.get_forecast(session, req)
        assert len(res.timeline) == 3
        # Check sorting
        assert [item.minutes_ahead for item in res.timeline] == [30, 60, 120]
        for item in res.timeline:
            assert item.target_time > res.base_time
            assert item.predicted_speed > 0
            assert 1 <= item.congestion_level <= 4


def test_prediction_timezone_handling_utc_to_hanoi():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        node1 = Node(node_code="N1", node_name="N1", district="D1", latitude=21.0, longitude=105.8)
        node2 = Node(node_code="N2", node_name="N2", district="D2", latitude=21.01, longitude=105.81)
        session.add_all([node1, node2])
        session.commit()
        session.refresh(node1)
        session.refresh(node2)

        edge = Edge(
            edge_code="E_TZ",
            street_name="Timezone Street",
            from_node_id=node1.node_id,
            to_node_id=node2.node_id,
            length_km=2.0,
            max_speed_limit=50,
        )
        session.add(edge)
        session.commit()
        session.refresh(edge)

        # 10:30 UTC = 17:30 Hanoi time (Vietnam is UTC+7)
        # Adding 30 mins -> 18:00 Hanoi time (Rush hour!)
        utc_base = datetime(2026, 11, 9, 10, 30, tzinfo=UTC)
        req = PredictionRequest(
            edge_id=edge.edge_id,
            base_time=utc_base,
            minutes_ahead=[30],
        )
        res = PredictionService.get_forecast(session, req)
        assert len(res.timeline) == 1
        item = res.timeline[0]
        # In Hanoi time, 10:30 UTC + 30m = 18:00 Hanoi, so hour_of_day should be 18
        assert item.hour_of_day == 18

        # Also verify cache DB persistence
        cached = session.exec(
            select(Prediction).where(
                Prediction.edge_id == edge.edge_id,
                Prediction.hour_of_day == 18,
            )
        ).first()
        assert cached is not None
        assert cached.predicted_speed == item.predicted_speed





def test_prediction_lifecycle_and_validation():
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
            email="admin_pred@example.com",
            password_hash="pw",
            full_name="Admin Pred",
            role="admin",
        )
        node1 = Node(
            node_code="NODE_A",
            node_name="Node A",
            district="District A",
            latitude=21.0,
            longitude=105.8,
        )
        node2 = Node(
            node_code="NODE_B",
            node_name="Node B",
            district="District B",
            latitude=21.01,
            longitude=105.81,
        )
        session.add_all([admin, node1, node2])
        session.commit()
        session.refresh(admin)
        session.refresh(node1)
        session.refresh(node2)

        edge = Edge(
            edge_code="EDGE_PRED",
            street_name="Prediction Street",
            from_node_id=node1.node_id,
            to_node_id=node2.node_id,
            length_km=3.0,
            max_speed_limit=50,
        )
        session.add(edge)
        session.commit()
        session.refresh(edge)

        admin_token = create_access_token({"sub": str(admin.user_id), "role": "admin"})

    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    with TestClient(app) as client:
        # 1. Invalid minutes_ahead validation (negative, empty, > 1440 -> 422)
        res_invalid_neg = client.post(
            "/api/v1/predictions/forecast",
            json={"edge_id": str(edge.edge_id), "minutes_ahead": [-10]},
        )
        assert res_invalid_neg.status_code == 422

        res_invalid_empty = client.post(
            "/api/v1/predictions/forecast",
            json={"edge_id": str(edge.edge_id), "minutes_ahead": []},
        )
        assert res_invalid_empty.status_code == 422

        res_invalid_large = client.post(
            "/api/v1/predictions/forecast",
            json={"edge_id": str(edge.edge_id), "minutes_ahead": [2000]},
        )
        assert res_invalid_large.status_code == 422

        # 2. Valid default forecast request (no minutes_ahead provided -> defaults to [30, 60, 120])
        res_default = client.post(
            "/api/v1/predictions/forecast",
            json={"edge_id": str(edge.edge_id), "weather": "rain"},
        )
        assert res_default.status_code == 200
        data_default = res_default.json()["data"]
        assert data_default["edge_id"] == str(edge.edge_id)
        assert data_default["street_name"] == "Prediction Street"
        assert len(data_default["timeline"]) == 3
        assert [item["minutes_ahead"] for item in data_default["timeline"]] == [30, 60, 120]
        for item in data_default["timeline"]:
            assert item["predicted_speed"] > 0
            assert 0.0 <= item["risk_factor"] <= 1.0
            assert 1 <= item["congestion_level"] <= 4

        # 3. Valid custom timeline forecast request with street_name and unsorted minutes
        res_custom = client.post(
            "/api/v1/predictions/forecast",
            json={"street_name": "Prediction Street", "minutes_ahead": [90, 15, 45]},
        )
        assert res_custom.status_code == 200
        data_custom = res_custom.json()["data"]
        assert len(data_custom["timeline"]) == 3
        # Must be sorted
        assert [item["minutes_ahead"] for item in data_custom["timeline"]] == [15, 45, 90]

        # 4. Non-existent edge -> 404
        random_uuid = str(uuid.uuid4())
        res_not_found = client.post(
            "/api/v1/predictions/forecast",
            json={"edge_id": random_uuid},
        )
        assert res_not_found.status_code == 404

        # 5. Admin triggers retrain
        res_retrain = client.post("/api/v1/admin/retrain-model", headers=admin_headers)
        assert res_retrain.status_code == 200
        assert "tiến trình ngầm" in res_retrain.json()["message"]

    app.dependency_overrides.clear()
