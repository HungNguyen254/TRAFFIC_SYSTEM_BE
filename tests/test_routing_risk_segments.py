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
FROZEN_NOW = datetime(
    2026, 11, 16, 10, 30, tzinfo=LOCAL_TZ
)  # Thứ 2, 10h, ngoài cao điểm


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
        nodes = [
            Node(
                node_id=uuid.uuid4(),
                node_code=f"N{i}",
                node_name=f"Nút {i}",
                district="Quận Test",
                latitude=21.0 + i * 0.01,
                longitude=105.8 + i * 0.01,
            )
            for i in range(4)
        ]
        edges = [
            Edge(
                edge_id=uuid.uuid4(),
                edge_code="E_A1",
                street_name="Phố A",
                from_node_id=nodes[0].node_id,
                to_node_id=nodes[1].node_id,
                length_km=1.0,
                max_speed_limit=50,
            ),
            Edge(
                edge_id=uuid.uuid4(),
                edge_code="E_A2",
                street_name="Phố A",
                from_node_id=nodes[1].node_id,
                to_node_id=nodes[2].node_id,
                length_km=1.5,
                max_speed_limit=50,
            ),
            Edge(
                edge_id=uuid.uuid4(),
                edge_code="E_B1",
                street_name="Phố B",
                from_node_id=nodes[2].node_id,
                to_node_id=nodes[3].node_id,
                length_km=2.0,
                max_speed_limit=50,
            ),
        ]
        session.add_all([*nodes, *edges])
        session.commit()

        graph = build_graph(session, weight_mode="duration")
        route = find_route(graph, nodes[0].node_id, nodes[3].node_id)
        yield session, edges, route

    clear_graph_cache()
    clear_traffic_data_cache()


def _set_speed(session: Session, edge: Edge, speed: float) -> None:
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


def test_marks_risky_steps_and_merges_consecutive_same_street(env):
    session, edges, route = env
    _set_speed(session, edges[0], 20.0)  # level 3
    _set_speed(session, edges[1], 20.0)  # level 3, cùng tên đường -> gộp
    _set_speed(session, edges[2], 10.0)  # level 4

    apply_speed_source(session, route, "current")

    assert [step.at_risk for step in route.steps] == [True, True, True]
    assert len(route.risk_segments) == 2
    first, second = route.risk_segments
    assert first.street_name == "Phố A"
    assert first.congestion_level == 3
    assert first.level_label == "Ùn tắc nghiêm trọng"
    assert first.edge_ids == [edges[0].edge_id, edges[1].edge_id]
    assert first.length_km == 2.5
    assert second.street_name == "Phố B"
    assert second.congestion_level == 4
    assert second.level_label == "Kẹt xe hoàn toàn"
    assert "2 đoạn nguy cơ tắc cao" in route.risk_warning
    assert "Phố A" in route.risk_warning
    assert "Phố B" in route.risk_warning


def test_safe_route_has_no_risk_warning(env):
    session, edges, route = env
    for edge in edges:
        _set_speed(session, edge, 40.0)  # level 1

    apply_speed_source(session, route, "current")

    assert [step.at_risk for step in route.steps] == [False, False, False]
    assert route.risk_segments == []
    assert route.risk_warning == ""


def test_limit_mode_never_flags_risk(env):
    session, _edges, route = env
    apply_speed_source(session, route, "limit")

    assert [step.at_risk for step in route.steps] == [False, False, False]
    assert route.risk_segments == []
    assert route.risk_warning == ""


def test_same_street_not_merged_when_not_consecutive(env):
    session, edges, route = env
    _set_speed(session, edges[0], 20.0)  # Phố A, level 3
    _set_speed(session, edges[1], 40.0)  # Phố A, level 1
    _set_speed(session, edges[2], 10.0)  # Phố B, level 4

    apply_speed_source(session, route, "current")

    assert [step.at_risk for step in route.steps] == [True, False, True]
    assert [seg.street_name for seg in route.risk_segments] == ["Phố A", "Phố B"]
    assert route.risk_segments[0].edge_ids == [edges[0].edge_id]
