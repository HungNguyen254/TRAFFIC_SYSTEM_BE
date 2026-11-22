import json

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.exceptions import BadRequestException
from app.models.edge import Edge
from app.models.node import Node
from app.schemas.admin_road import AdminRoadPayload
from app.services.traffic_service import TrafficService


def create_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def make_road_payload(**overrides):
    values = {
        "edge_code": "ADMIN-ROAD-1",
        "street_name": "Đường demo",
        "district": "Cầu Giấy",
        "max_speed_limit": 50,
        "coordinates": [
            {"lat": 21.03, "lng": 105.78},
            {"lat": 21.031, "lng": 105.782},
            {"lat": 21.032, "lng": 105.784},
        ],
    }
    values.update(overrides)
    return AdminRoadPayload(**values)


def test_admin_road_create_update_delete_manages_its_endpoint_nodes():
    engine = create_test_engine()
    with Session(engine) as session:
        created = TrafficService.create_admin_road(
            session, make_road_payload()
        )
        edge = session.get(Edge, created.edge_id)

        assert edge is not None
        expected_coordinates = [
            [105.78, 21.03],
            [105.782, 21.031],
            [105.784, 21.032],
        ]
        assert json.loads(edge.geom)["coordinates"] == expected_coordinates
        assert len(session.exec(select(Node)).all()) == 2
        assert created.length_km > 0
        assert created.has_geometry is True

        traffic_data = TrafficService.get_edges_with_traffic(
            session, hour_of_day=12, day_of_week=0
        )
        assert traffic_data["edges"][0]["geom"] == edge.geom

        updated_payload = make_road_payload(
            street_name="Đường demo đã sửa",
            coordinates=[
                {"lat": 21.04, "lng": 105.79},
                {"lat": 21.041, "lng": 105.792},
            ],
        )
        updated = TrafficService.update_admin_road(
            session, created.edge_id, updated_payload
        )
        assert updated.street_name == "Đường demo đã sửa"
        assert len(updated.coordinates) == 2
        assert len(session.exec(select(Node)).all()) == 2

        listing = TrafficService.get_admin_roads(session)
        assert [road.edge_id for road in listing.roads] == [created.edge_id]
        assert listing.districts == ["Cầu Giấy"]

        edge.geom = None
        session.add(edge)
        session.commit()
        road_without_geometry = TrafficService.get_admin_roads(session).roads[0]
        assert road_without_geometry.has_geometry is False
        assert len(road_without_geometry.coordinates) == 2

        TrafficService.delete_admin_road(session, created.edge_id)
        assert session.exec(select(Edge)).all() == []
        assert session.exec(select(Node)).all() == []


def test_admin_road_rejects_duplicate_codes_before_creating_nodes():
    engine = create_test_engine()
    with Session(engine) as session:
        TrafficService.create_admin_road(session, make_road_payload())

        with pytest.raises(BadRequestException, match="đã tồn tại"):
            TrafficService.create_admin_road(session, make_road_payload())

        assert len(session.exec(select(Node)).all()) == 2


def test_admin_road_requires_distinct_endpoint_coordinates():
    with pytest.raises(ValueError, match="Điểm đầu và điểm cuối"):
        make_road_payload(
            coordinates=[
                {"lat": 21.03, "lng": 105.78},
                {"lat": 21.031, "lng": 105.782},
                {"lat": 21.03, "lng": 105.78},
            ]
        )
