import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.edge import Edge
from app.models.node import Node
from app.models.traffic_data import TrafficData
from app.services import routing_service
from app.services.routing_service import (
    build_graph,
    clear_graph_cache,
    find_route,
    find_route_alternatives,
)
from app.services.traffic_service import clear_traffic_data_cache

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
# Thứ 2, 10:30 — ngoài giờ cao điểm
FROZEN_NOW = datetime(2026, 11, 16, 10, 30, tzinfo=LOCAL_TZ)


class _FrozenDatetime:
    @classmethod
    def now(cls, tz=None):
        return FROZEN_NOW


@pytest.fixture
def session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.core.database.engine", engine)
    monkeypatch.setattr(routing_service, "datetime", _FrozenDatetime)
    clear_graph_cache()
    clear_traffic_data_cache()
    with Session(engine) as db_session:
        yield db_session
    clear_graph_cache()
    clear_traffic_data_cache()


def _node(db_session: Session, code: str) -> Node:
    node = Node(
        node_id=uuid.uuid4(), node_code=code, node_name=code, district="Quận Test",
        latitude=21.0, longitude=105.8,
    )
    db_session.add(node)
    db_session.commit()
    return node


def _edge(
    db_session: Session, from_node: Node, to_node: Node, code: str,
    length_km: float, limit: int = 50,
) -> Edge:
    edge = Edge(
        edge_id=uuid.uuid4(), edge_code=code, street_name=code,
        from_node_id=from_node.node_id, to_node_id=to_node.node_id,
        length_km=length_km, max_speed_limit=limit,
    )
    db_session.add(edge)
    db_session.commit()
    return edge


def _traffic(db_session: Session, edge: Edge, speed: float) -> None:
    db_session.add(
        TrafficData(
            edge_code=edge.edge_code, street_name=edge.street_name,
            length_km=edge.length_km, max_speed_limit=edge.max_speed_limit,
            hour_of_day=FROZEN_NOW.hour, day_of_week=FROZEN_NOW.weekday(),
            is_weekend=0, is_rush_hour=0, weather_code=0.0,
            average_speed=speed, congestion_level=2, risk_factor=0.5,
        )
    )
    db_session.commit()
    clear_traffic_data_cache()


def _diamond(db_session: Session):
    """3 tuyến song song từ origin tới destination.

    A: 2 cạnh 2.0 km (tĩnh 4.8 phút) - ngắn nhất nên là tuyến chính
    B: 3 cạnh 2.5 km (tĩnh 9.0 phút)
    C: 2 cạnh 3.0 km (tĩnh 7.2 phút)
    """
    origin, dest = _node(db_session, "O"), _node(db_session, "D")
    a1 = _node(db_session, "A1")
    b1, b2 = _node(db_session, "B1"), _node(db_session, "B2")
    c1 = _node(db_session, "C1")

    edges_a = [_edge(db_session, origin, a1, "A_IN", 2.0), _edge(db_session, a1, dest, "A_OUT", 2.0)]
    edges_b = [
        _edge(db_session, origin, b1, "B_IN", 2.5),
        _edge(db_session, b1, b2, "B_MID", 2.5),
        _edge(db_session, b2, dest, "B_OUT", 2.5),
    ]
    edges_c = [_edge(db_session, origin, c1, "C_IN", 3.0), _edge(db_session, c1, dest, "C_OUT", 3.0)]
    return origin, dest, edges_a, edges_b, edges_c


def test_route_alternatives_offers_options_when_main_route_at_risk(session):
    origin, dest, edges_a, edges_b, edges_c = _diamond(session)
    for edge in edges_a:
        _traffic(session, edge, speed=10.0)  # level 4 -> tắc
    for edge in edges_b:
        _traffic(session, edge, speed=30.0)  # level 2
    for edge in edges_c:
        _traffic(session, edge, speed=40.0)  # level 1

    result = find_route_alternatives(session, origin.node_id, dest.node_id, "current")

    assert result.main_route_at_risk is True
    assert result.has_alternative is True
    assert len(result.options) == 3

    main, alt1, alt2 = result.options
    assert main.at_risk is True
    assert main.congestion_level == pytest.approx(4.0)
    assert main.route.total_duration_min == pytest.approx(24.0)

    # Alternatives được sắp theo ETA tăng dần: C (9.0) rồi B (15.0)
    assert alt1.congestion_level == pytest.approx(1.0)
    assert alt1.route.total_duration_min == pytest.approx(9.0)
    assert alt2.route.total_duration_min == pytest.approx(15.0)


def test_route_alternatives_stops_at_one_option_when_main_route_clear(session):
    origin, dest, edges_a, edges_b, _ = _diamond(session)
    for edge in edges_a:
        _traffic(session, edge, speed=40.0)
    for edge in edges_b:
        _traffic(session, edge, speed=10.0)

    result = find_route_alternatives(session, origin.node_id, dest.node_id, "current")

    assert result.main_route_at_risk is False
    assert result.has_alternative is False
    assert len(result.options) == 1
    assert result.options[0].route.total_duration_min == pytest.approx(6.0)


def test_route_alternatives_reports_when_no_other_route_exists(session):
    origin, dest = _node(session, "O"), _node(session, "D")
    mid = _node(session, "M")
    e_in = _edge(session, origin, mid, "X_IN", 2.0)
    e_out = _edge(session, mid, dest, "X_OUT", 2.0)
    for edge in (e_in, e_out):
        _traffic(session, edge, speed=10.0)

    result = find_route_alternatives(session, origin.node_id, dest.node_id, "current")

    assert result.main_route_at_risk is True
    assert result.has_alternative is False
    assert len(result.options) == 1
    assert "Không tìm thấy tuyến đường khác" in result.message


def test_route_alternatives_caps_options_at_three(session):
    origin, dest, edges_a, edges_b, edges_c = _diamond(session)
    d1 = _node(session, "D1")
    edges_d = [
        _edge(session, origin, d1, "D_IN", 2.2),
        _edge(session, d1, dest, "D_OUT", 2.2),
    ]
    for edge in edges_a + edges_b + edges_c + edges_d:
        _traffic(session, edge, speed=10.0)

    result = find_route_alternatives(session, origin.node_id, dest.node_id, "current")

    assert result.main_route_at_risk is True
    assert len(result.options) == 3


def test_route_alternatives_marks_congestion_per_step(session):
    origin, dest, edges_a, _, _ = _diamond(session)
    for edge in edges_a:
        _traffic(session, edge, speed=10.0)

    graph = build_graph(session, "duration")
    route = find_route(graph, origin.node_id, dest.node_id)
    result = find_route_alternatives(session, origin.node_id, dest.node_id, "current")

    main_steps = result.options[0].route.steps
    assert len(main_steps) == len(route.steps)
    assert all(step.congestion_level == 4 for step in main_steps)
