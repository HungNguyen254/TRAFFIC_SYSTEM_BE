import uuid
from sqlmodel import Session, SQLModel, create_engine

from app.models.edge import Edge
from app.models.traffic_data import TrafficData
from app.services.traffic_service import TrafficService, clear_traffic_data_cache


def test_traffic_service_loads_snapshot_from_database(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.core.database.engine", engine)
    clear_traffic_data_cache()

    edge = Edge(
        edge_id=uuid.uuid4(),
        edge_code="EDGE_DB_TEST",
        street_name="Pho Hue",
        from_node_id=uuid.uuid4(),
        to_node_id=uuid.uuid4(),
        length_km=1.5,
        max_speed_limit=50,
    )

    with Session(engine) as session:
        # Add sample traffic data
        session.add(
            TrafficData(
                edge_code="EDGE_DB_TEST",
                street_name="Pho Hue",
                length_km=1.5,
                max_speed_limit=50,
                hour_of_day=8,
                day_of_week=1,
                is_weekend=0,
                is_rush_hour=1,
                weather_code=0.0,
                average_speed=20.0,
                congestion_level=3,
                risk_factor=0.6,
            )
        )
        session.commit()

        # Get snapshot for exact match: hour=8, day=1
        snapshot = TrafficService.get_edge_traffic_snapshot(edge=edge, hour_of_day=8, day_of_week=1, session=session)
        assert snapshot["speed"] == 20.0
        assert snapshot["congestion_level"] == 3


def test_traffic_service_fallback_to_default_when_no_records_in_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.core.database.engine", engine)
    clear_traffic_data_cache()

    edge = Edge(
        edge_id=uuid.uuid4(),
        edge_code="EDGE_NO_DATA",
        street_name="Pho Hue",
        from_node_id=uuid.uuid4(),
        to_node_id=uuid.uuid4(),
        length_km=2.0,
        max_speed_limit=60,
    )

    with Session(engine) as session:
        snapshot = TrafficService.get_edge_traffic_snapshot(edge=edge, hour_of_day=10, day_of_week=2, session=session)
        # Default speed is max_speed_limit * 0.7 = 42.0
        assert snapshot["speed"] == 42.0
        assert snapshot["congestion_level"] == 1
