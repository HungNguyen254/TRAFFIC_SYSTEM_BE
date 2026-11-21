from types import SimpleNamespace

import numpy as np
from sqlmodel import Session, SQLModel, create_engine

from app.models.edge import Edge
from app.models.node import Node
from app.schemas.prediction import MapForecastRequest
from app.services.prediction_service import PredictionService


class _Estimator:
    def __init__(self, value: float):
        self.value = value

    def predict(self, features):
        return np.array([self.value])


class _Ensemble:
    estimators_ = [_Estimator(40), _Estimator(30)]

    def predict(self, features):
        return np.array([35.0])


def test_ensemble_agreement_is_normalized_tree_consensus(monkeypatch):
    model = SimpleNamespace(estimators_=[_Estimator(40), _Estimator(30)])
    monkeypatch.setattr(PredictionService, "_model", model)
    edge = SimpleNamespace(length_km=1.0, max_speed_limit=50)

    agreement = PredictionService._compute_ensemble_agreement(
        edge=edge,
        hour_of_day=12,
        day_of_week=1,
        weather="sunny",
    )

    assert agreement == 0.9


def test_ensemble_agreement_is_unavailable_without_a_forest_model(monkeypatch):
    monkeypatch.setattr(PredictionService, "_model", None)
    edge = SimpleNamespace(length_km=1.0, max_speed_limit=50)

    agreement = PredictionService._compute_ensemble_agreement(
        edge=edge,
        hour_of_day=12,
        day_of_week=1,
        weather="sunny",
    )

    assert agreement is None


def test_map_forecast_response_includes_agreement_and_prediction_source(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(PredictionService, "_model", _Ensemble())

    node_a = Node(
        node_code="FORECAST_A",
        node_name="Forecast A",
        district="Test",
        latitude=21.0,
        longitude=105.0,
    )
    node_b = Node(
        node_code="FORECAST_B",
        node_name="Forecast B",
        district="Test",
        latitude=21.1,
        longitude=105.1,
    )
    edge = Edge(
        edge_code="FORECAST_EDGE",
        street_name="Phố dự báo",
        from_node_id=node_a.node_id,
        to_node_id=node_b.node_id,
        length_km=1.0,
        max_speed_limit=50,
    )

    with Session(engine) as session:
        session.add_all([node_a, node_b, edge])
        session.commit()

        forecast = PredictionService.get_map_forecast(
            session,
            MapForecastRequest(minutes_ahead=30),
        )

    assert forecast.prediction_source == "machine_learning"
    assert len(forecast.edges) == 1
    assert forecast.edges[0].ensemble_agreement == 0.9
