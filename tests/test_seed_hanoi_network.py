from datetime import datetime

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from app.models.edge import Edge
from app.models.traffic_data import TrafficData
from app.services.traffic_service import TrafficService
from scripts.seed_hanoi_network import HANOI_EDGES, seed_network


def test_seed_network_adds_complete_traffic_profiles_and_chart_data():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with Session(engine) as session:
        seed_network(session)

        edge = session.exec(select(Edge).where(Edge.edge_code == HANOI_EDGES[0]["edge_code"])).one()
        history = TrafficService.get_edge_hourly_history(
            session,
            edge.edge_id,
            datetime(2026, 11, 9, 7),
            datetime(2026, 11, 9, 10),
        )

        assert history.total_hours == 3
        assert history.hours_with_data == 3
        assert all(bucket.average_speed is not None for bucket in history.buckets)
        assert all(bucket.sample_count == 1 for bucket in history.buckets)

        first_count = len(session.exec(select(TrafficData.id)).all())
        assert first_count == len(HANOI_EDGES) * 7 * 24

        seed_network(session)
        assert len(session.exec(select(TrafficData.id)).all()) == first_count
