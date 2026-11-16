import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.edge import Edge
from app.models.node import Node
from app.models.traffic_data import TrafficData
from app.services import routing_service
from app.services.prediction_service import PredictionService
from app.services.routing_service import (
    apply_speed_source,
    build_graph,
    clear_graph_cache,
    find_route,
)
from app.services.traffic_service import clear_traffic_data_cache

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
FROZEN_NOW = datetime(2026, 11, 16, 10, 30, tzinfo=LOCAL_TZ)  # Thứ 2, 10h, ngoài giờ cao điểm


class _FrozenDatetime:
    @classmethod
    def now(cls, tz=None):
        return FROZEN_NOW


@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.core.database.engine", engine)
    monkeypatch.setattr(routing_service, "datetime", _FrozenDatetime)
    monkeypatch.setattr(PredictionService, "_model", None)
    clear_graph_cache()
    clear_traffic_data_cache()

    with Session(engine) as session:
        node1 = Node(
            node_id=uuid.uuid4(), node_code="N1", node_name="Nút 1", district="Quận Test",
            latitude=21.0, longitude=105.8,
        )
        node2 = Node(
            node_id=uuid.uuid4(), node_code="N2", node_name="Nút 2", district="Quận Test",
            latitude=21.1, longitude=105.9,
        )
        edge = Edge(
            edge_id=uuid.uuid4(), edge_code="E_SPEED", street_name="Phố Test",
            from_node_id=node1.node_id, to_node_id=node2.node_id,
            length_km=2.0, max_speed_limit=50,
        )
        session.add_all([node1, node2, edge])
        session.commit()

        graph = build_graph(session, weight_mode="duration")
        route = find_route(graph, node1.node_id, node2.node_id)
        yield session, edge, route

    clear_graph_cache()
    clear_traffic_data_cache()


def _add_traffic(session: Session, edge: Edge, speed: float) -> None:
    session.add(
        TrafficData(
            edge_code=edge.edge_code,
            street_name=edge.street_name,
            length_km=edge.length_km,
            max_speed_limit=edge.max_speed_limit,
            hour_of_day=FROZEN_NOW.hour,
            day_of_week=FROZEN_NOW.weekday(),
            is_weekend=0,
            is_rush_hour=0,
            weather_code=0.0,
            average_speed=speed,
            congestion_level=2,
            risk_factor=0.5,
        )
    )
    session.commit()
    clear_traffic_data_cache()


def test_limit_keeps_fixed_speed_eta(env):
    session, edge, route = env
    apply_speed_source(session, route, "limit")
    assert route.steps[0].speed_kmh == 50.0
    assert route.steps[0].travel_min == 2.4
    assert route.total_duration_min == 2.4


def test_current_uses_traffic_data_speed(env):
    session, edge, route = env
    _add_traffic(session, edge, speed=20.0)
    apply_speed_source(session, route, "current")
    assert route.steps[0].speed_kmh == 20.0
    assert route.steps[0].travel_min == 6.0
    assert route.total_duration_min == 6.0


def test_current_falls_back_when_no_traffic_data(env):
    session, edge, route = env
    apply_speed_source(session, route, "current")
    # Snapshot fallback: 0.7 * 50 = 35 km/h
    assert route.steps[0].speed_kmh == 35.0
    assert route.steps[0].travel_min == round(2.0 / 35.0 * 60, 2)


def test_forecast_uses_heuristic_when_no_model(env):
    session, edge, route = env
    apply_speed_source(session, route, "forecast")
    # Heuristic: ngoài cao điểm, ngày thường, nắng -> 0.85 * 50 = 42.5
    assert route.steps[0].speed_kmh == 42.5
    assert route.steps[0].travel_min == round(2.0 / 42.5 * 60, 2)


def test_current_clamps_speed_to_limit(env):
    session, edge, route = env
    _add_traffic(session, edge, speed=120.0)
    apply_speed_source(session, route, "current")
    assert route.steps[0].speed_kmh == 50.0
    assert route.steps[0].travel_min == 2.4


def test_current_clamps_speed_to_min(env):
    session, edge, route = env
    _add_traffic(session, edge, speed=0.2)
    apply_speed_source(session, route, "current")
    assert route.steps[0].speed_kmh == 1.0
    assert route.steps[0].travel_min == 120.0