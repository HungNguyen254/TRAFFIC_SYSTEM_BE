import uuid
from datetime import UTC, datetime

from sqlmodel import Session, SQLModel, create_engine

from app.models.edge import Edge
from app.models.node import Node
from app.schemas.prediction import RouteForecastRequest
from app.services.prediction_service import PredictionService


def test_route_forecast_accumulates_predicted_eta_for_later_edges(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    origin_id = uuid.uuid4()
    middle_id = uuid.uuid4()
    destination_id = uuid.uuid4()
    first_edge_id = uuid.uuid4()
    second_edge_id = uuid.uuid4()

    with Session(engine) as session:
        session.add_all(
            [
                Node(
                    node_id=origin_id,
                    node_code="ORIGIN",
                    node_name="Origin",
                    district="Test",
                    latitude=21,
                    longitude=105,
                ),
                Node(
                    node_id=middle_id,
                    node_code="MIDDLE",
                    node_name="Middle",
                    district="Test",
                    latitude=21.1,
                    longitude=105.1,
                ),
                Node(
                    node_id=destination_id,
                    node_code="DEST",
                    node_name="Destination",
                    district="Test",
                    latitude=21.2,
                    longitude=105.2,
                ),
                Edge(
                    edge_id=first_edge_id,
                    edge_code="EDGE-1",
                    street_name="First",
                    from_node_id=origin_id,
                    to_node_id=middle_id,
                    length_km=5,
                    max_speed_limit=50,
                ),
                Edge(
                    edge_id=second_edge_id,
                    edge_code="EDGE-2",
                    street_name="Second",
                    from_node_id=middle_id,
                    to_node_id=destination_id,
                    length_km=10,
                    max_speed_limit=50,
                ),
            ]
        )
        session.commit()

        offsets = []

        def fake_prediction_values(edge, hour_of_day, day_of_week, weather):
            offsets.append((edge.edge_id, hour_of_day, day_of_week, weather))
            return (30.0, 0.4, 2, "Forecast")

        monkeypatch.setattr(
            PredictionService,
            "_compute_prediction_values",
            fake_prediction_values,
        )
        result = PredictionService.get_route_forecast(
            session,
            RouteForecastRequest(
                base_time=datetime(2026, 11, 22, 0, 0, tzinfo=UTC),
                weather="rain",
                steps=[
                    {"edge_id": first_edge_id, "baseline_travel_min": 10},
                    {"edge_id": second_edge_id, "baseline_travel_min": 10},
                ],
            ),
        )

    assert [step.edge_id for step in result.steps] == [first_edge_id, second_edge_id]
    assert [step.minutes_ahead for step in result.steps] == [5, 15]
    assert [step.predicted_minutes for step in result.steps] == [10, 20]
    assert result.predicted_duration_min == 30
